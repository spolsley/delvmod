#!/usr/bin/env python
# Copyright 2015-6 Bryce Schroeder, www.bryce.pw, bryce.schroeder@gmail.com
# 
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# "Cythera" and "Delver" are trademarks of either Glenn Andreas or 
# Ambrosia Software, Inc. 
import delv
import delv.archive, delv.library
import gobject

version = '0.2.2'
PATCHINFO = """Created with redelv %s, based on the delv library."""%version
MSG_NO_UNDERLAY = """Couldn't create library; if you are editing a saved game, 
you need to underlay a scenario. Exception was: %s"""
ABOUT_TEXT = """<span font_family="monospace">
    This program is free software: you can redistribute it and/or modify 
    it under the terms of the GNU General Public License as published by 
    the Free Software Foundation, either version 3 of the License, or 
    (at your option) any later version. 

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of 
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License 
    along with this program.  If not, see <a href="http://www.gnu.org/licenses/">the GNU website</a>.
</span>
 <i>Cythera</i> and <i>Delver</i> are trademarks of either Glenn Andreas or Ambrosia Software, Inc. 
 redelv is copyright 2015-16 Bryce Schroeder, bryce.schroeder@gmail.com, <a href="http://www.bryce.pw/">bryce.pw</a>
 Based on the <a href="http://www.ferazelhosting.net/wiki/delv">delv</a> Python module. Repository: <a href="https://github.com/BryceSchroeder/delvmod/">GitHub</a> 
delv version %s, redelv version %s
"""%(delv.version,version)

import pygtk
pygtk.require('2.0')
import gtk, os, sys, gobject, tempfile, subprocess, datetime
import json
import images, editgui
DEFAULT_PREFS = {# Command that will play sounds:
                   'play_sound_cmd': 'mplayer %s', 
                   # Enter the command for your hex editor here, e.g. ghex
                   'hex_editor_cmd': 'bless %s',
                   'graphics_editor_cmd': 'gimp -n %s',
                   'audio_editor_cmd': 'audacity %s',
                   'assembly_editor_cmd': 'gedit --standalone %s',

                   # If True, when an external editor edits a file open in
                   # an active editor, propagate those changes immediately
                   # (this generally looks pretty cool, but it may hose your
                   #  unsaved changes if any.)
                   'instant_editor_propagation':True,

                   # This is the info to add to patches produced.
                   'default_patch_info':PATCHINFO,

                   # URL form to retrieve human-checked source code from
                   'source_archive':  
                       'http://www.ferazelhosting.net/wiki/%04X?action=raw',
                   }
PREFS_PATH = os.path.expanduser('~/.redelv')

class AskNewResourceBox(gtk.Dialog):
    def __init__(self,redelv,prompt="Create a new resource:"):
        self.redelv=redelv
        gtk.Dialog.__init__(self)
        v = gtk.Label(prompt)
        self.vbox.pack_start(v)
        v.show()
        self.e = gtk.Entry(max=6)
        self.e.set_text("0x%04X"%self.redelv.get_new_resid(self.redelv.current_subindex_id))
        self.vbox.pack_start(self.e)
        self.e.show()
        #self.resid = 
        #self.name = 
        self.add_buttons(gtk.STOCK_NEW, 1, gtk.STOCK_CANCEL, 0)

        self.vbox.show()
    def get_value(self):
        return int(self.e.get_text().replace('0x',''),16)

class ReDelv(object):
    def get_new_resid(self, si):
        if si == 0: return 0
        for r in xrange(1,254): 
            if not self.archive.get((si,r)): return ((si+1)<<8)|r
        return ((si+1)<<8)

    def __init__(self):
        if os.path.exists(PREFS_PATH):
            self.preferences = json.load(open(PREFS_PATH))
            for key in DEFAULT_PREFS.keys():
                if not self.preferences.has_key(key):
                    self.preferences[key] = DEFAULT_PREFS[key]
        else:
            self.preferences = DEFAULT_PREFS
            json.dump(self.preferences, open(PREFS_PATH,'wb'),indent=True)
        self.base_archive=None
        self.patch_base=None
        self.library = None
        self.underlay = None
        self.patch_output_path=None
        self.hex_editors_open = {}
        self.queued_changes = []
        self.tempfile_references = {}
        self.timeout_sid = None
        # Signals 
        self.open_editors = {}
        self.filechange = []
        self.subindexchange = []
        self.resourcechange = []
        self.archive = None
        self.library = None
        #gobject.type_register(editgui.Receiver)
        #gobject.signal_new("filechange", editgui.Receiver, 
        #    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
        # Windows and globals
        self._unsaved = False
        self.opened_file = None
        self.exported_directory = None
        self.current_resource = None
        self.current_resource_id = 0
        self.current_subindex_id = 0
        self.aboutbox = None
        self.file_metadata_window = None
        self.file_get_info_window = None

        # Make the main window
        self.clipboard = gtk.clipboard_get()
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(480,512)
        self.window.set_title("redelv - [No File Open]")
        self.window.set_icon(gtk.gdk.pixbuf_new_from_file(images.icon_path))
        
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.mvbox = gtk.VBox(homogeneous=False,spacing=0)
        self.window.add(self.mvbox)

        # Make the menu
        menu_items = (
            ("/_File",           None,          None,           0,  "<Branch>"),
            ("/File/_New",       "<control>N",  self.menu_new,  0,  None),
            ("/File/_Open",      "<control>O",  self.menu_open, 0,  None),
            ("/File/_Save",      "<control>S",  self.menu_save, 0,  None),
            ("/File/_Save _Copy",None,          self.menu_save_copy,0,None),
            ("/File/_Save _As",None,          self.menu_save_as,0,None),
            ("/File/sep1",       None,          None,          0,"<Separator>"),
            ("/File/_Import",    None,          self.menu_import,0, None),
            ("/File/_Export",    "<control>E",  self.menu_export,0, None),
            ("/File/_Export _As",None,          self.menu_export_as,0,None),
            ("/File/Underlay Scenario","<control>U",self.menu_underlay,0,None),
            ("/File/sep2",       None,          None,          0,"<Separator>"),
            ("/File/_Quit",      "<control>Q",  self.menu_quit ,0,  None),
 
            ("/_Edit",          None,           None,           0,  "<Branch>"),
            ("/Edit/_Get _Info","<control>I",   self.menu_get_info,0,None),
            ("/Edit/_File _Metadata",None,   self.menu_file_metadata,0,None),
            #("/Edit/_Create _Index",None,       self.menu_create_index,0,None),
            ("/Edit/sep3",       None,          None,          0,"<Separator>"),
            ("/Edit/_Delete",   "<control>K",     self.menu_delete,0,None),
            ("/Edit/_Create _Resource",None,  self.menu_create_resource,0,None),
            #("/Edit/_Export _Resource",None,  self.menu_export_resource,0,None),
            #("/Edit/_Import _Resource",None,  self.menu_import_resource,0,None),
            ("/Edit/sep4",       None,          None,          0,"<Separator>"),
            #("/Edit/_Cut",   "<control>X",           self.menu_cut,0,None),
            #("/Edit/_Copy",  "<control>C",           self.menu_copy,0,None),
            #("/Edit/_Paste", "<control>V",           self.menu_paste,0,None),
            ("/Edit/_Duplicate","<control>D",  self.menu_duplicate,0,None),

            ("/_Patch",          None,          None,          0, "<Branch>"),
            ("/Patch/_Select _Base",None,       self.menu_select_base,0,None),
            ("/Patch/_Save _Patch","<control>T",  self.menu_save_patch,0,None),
            ("/Patch/_Save _Patch _As",None,    self.menu_save_patch_as,0,None),
            ("/Patch/sep5",      None,          None,          0,"<Separator>"),
            ("/Patch/_Apply",None,              self.menu_apply,0,None),
            ("/Patch/_Check _Compatibility",None,
                 self.menu_check_compatibility,0,None),

            ("/_Tools",          None,           None,         0, "<Branch>"),
            ("/Tools/_Resource _Editor", 
                 "<control>R",self.menu_resource_editor,0,None),
            ("/Tools/_Use Specific Editor", None, None, 0, "<Branch>"),
            ("/Tools/Use Specific Editor/_Hex Editor", 
                 "<control>H",self.menu_hex_editor,0,None),
            ("/Tools/Use Specific Editor/sep01",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_Tile Sheet",None,
                 (lambda *argv: self.specific_ed("TileSheet")),0,None),
            ("/Tools/Use Specific Editor/_Portrait",None,
                 (lambda *argv: self.specific_ed("Portrait")),0,None),
            ("/Tools/Use Specific Editor/_Landscape",None,
                 (lambda *argv: self.specific_ed("Landscape")),0,None),
            ("/Tools/Use Specific Editor/_Sized Image",None,
                 (lambda *argv: self.specific_ed("Sized")),0,None),
            ("/Tools/Use Specific Editor/_Icon",None,
                 (lambda *argv: self.specific_ed("Icon")),0,None),
            ("/Tools/Use Specific Editor/sep02",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_Prop List",None,
                 (lambda *argv: self.specific_ed("PropList")),0,None),
            ("/Tools/Use Specific Editor/_Map",None,
                 (lambda *argv: self.specific_ed("Map")),0,None),
            ("/Tools/Use Specific Editor/sep03",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_Music",None,None,0,None),
            ("/Tools/Use Specific Editor/_Sound",None,
                 (lambda *argv: self.specific_ed("Sound")),0,None),
            ("/Tools/Use Specific Editor/sep04",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_Script Data",None,None,0,None),
            ("/Tools/Use Specific Editor/_Script",None,None,0,None),
            ("/Tools/Use Specific Editor/_AI Script",None,None,0,None),
            ("/Tools/Use Specific Editor/sep05",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_String List",None,None,0,None),
            ("/Tools/Use Specific Editor/_Symbols",None,None,0,None),
            ("/Tools/Use Specific Editor/sep06",None,None,0,"<Separator>"),
            ("/Tools/Use Specific Editor/_Patch",None,
                 (lambda *argv: self.specific_ed("Patch")),0,None),
            ("/Tools/Use Specific Editor/F0 Data Editors/Tile Name List",None,
                 (lambda *argv: self.specific_ed("TileNameList")),0,None),
            ("/Tools/Use Specific Editor/F0 Data Editors/Schedule",None,
                 (lambda *argv: self.specific_ed("ScheduleEditor")),0,None),
            ("/Tools/sep6", None, None, 0, "<Separator>"),
            ("/Tools/_Image _Browser", None, self.menu_image_browser,0,None),
            ("/Tools/High Level Editors/_Monsters",None,None,0,None),
            ("/Tools/High Level Editors/_Tiles",None,None,0,None),
            
            ("/_Help",           None,          None,           0, "<Branch>"),
            ("/Help/About",      None,          self.menu_about, 0, None),
        )
        accel = gtk.AccelGroup()
        ifc = gtk.ItemFactory(gtk.MenuBar, "<main>", accel)
        self.window.add_accel_group(accel)
        ifc.create_items(menu_items)
        self.menu_bar = ifc.get_widget("<main>")
        self.mvbox.pack_start(self.menu_bar, False, True, 0)

        # Make the data tree
        self.data_view = gtk.TreeView()
        dc1 = gtk.TreeViewColumn()
        dc1.set_title("Subindex") # Would it be so much to ask for this to be
        # in the constructor...
        dc2 = gtk.TreeViewColumn()
        dc2.set_title("Size")
        dc3 = gtk.TreeViewColumn()
        dc3.set_title("Description")
        
        # Seriously it's like GUI programming is designed to be as clunky
        # and non-functional as possible in the quest for generality
        # Why is there no truly native python gui kit? It's the most popular
        # language in the world now...
        # Aren't we ready to move beyond the state machine model for building
        # GUI stuff???
        # and why are all the RAD tools broken?! They could at least plaster
        # over this cruft...
        c =gtk.CellRendererText();dc1.pack_start(c,True);
        dc1.add_attribute(c,"text",0)
        c =gtk.CellRendererText();dc2.pack_start(c,True);
        dc2.add_attribute(c,"text",1)
        c =gtk.CellRendererText();dc3.pack_start(c,True);
        dc3.add_attribute(c,"text",2)         
        self.data_view.append_column(dc1)
        self.data_view.append_column(dc2)
        self.data_view.append_column(dc3)

        self.tree_data = gtk.TreeStore(str,str,str,int,int)
        self.data_view.set_model(self.tree_data)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        sw.add(self.data_view)
        self.mvbox.pack_start(sw, True, True, 0)


        self.data_view.connect("cursor-changed", self.cursor_changed)
        self.data_view.connect("row-activated", self.row_activated)




        self.window.show_all()
        if len(sys.argv) > 1: self.open_file(sys.argv[1])
        if len(sys.argv) > 2: self.underlay_archive(
            delv.archive.Scenario(sys.argv[2]))
    def main(self):
        gtk.main()
    def refresh_tree(self): 
        "Change the tree to reflect current data."
        print "WARNING: TreeView may be out of date."
        return

    def underlay_archive(self, archive):
        self.underlay = archive
    # Callbacks
    def row_activated(self, w, path, *argv):
        self.cursor_changed(w)
        if self.current_resource: self.menu_resource_editor(None)
        elif self.data_view.row_expanded(path): 
            self.data_view.collapse_row(path)
        else:
            self.data_view.expand_row(path,False)
    def cursor_changed(self, w, d=None):
        tm,crow = self.data_view.get_selection().get_selected_rows()
        crow = crow[-1]
        si = tm.get_value(tm.get_iter(crow), 3)
        rn = tm.get_value(tm.get_iter(crow), 4)
        if rn < 0:
            self.current_resource = None
            self.current_resource_id = 0
        else:
            self.current_resource_id = delv.archive.resid(si,rn)
            self.current_resource = self.get_library().get_resource(
                self.current_resource_id)
        self.current_subindex_id = si

        for recp in self.subindexchange: recp.signal_subindexchange()
        for recp in self.resourcechange: recp.signal_resourcechange()
    
    def menu_new(self, widget, data=None):
        #for recp in self.filechange: recp.signal_filechange()
        #for recp in self.subindexchange: recp.signal_subindexchange()
        #for recp in self.resourcechange: recp.signal_resourcechange()
        return None
    def is_unsaved(self):
        return self._unsaved
    def set_savedstate(self, v):
        if v: self.set_saved()
        else: self.set_unsaved()
    def set_saved(self):
        if self._unsaved: self.window.set_title(self.window.get_title()[10:])
        self._unsaved = False
    def set_unsaved(self):
        if not self._unsaved: 
            self.window.set_title('[unsaved] '+self.window.get_title())
        self._unsaved = True
    def menu_underlay(self, *argv):
        path = self.ask_open_path("Select a scenario to underlay...")
        if not path: return
        self.underlay_archive(delv.archive.Scenario(path))
    def ask_open_path(self,msg="Select a file..."):
        if self.is_unsaved() and self.warn_unsaved_changes(): return
        chooser = gtk.FileChooserDialog(title=msg,
                  action=gtk.FILE_CHOOSER_ACTION_OPEN,
                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                           gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            rv= chooser.get_filename()
        else: rv= None
        chooser.destroy()
        return rv
    def menu_open(self, widget, data=None):
        if self.is_unsaved() and self.warn_unsaved_changes(): return
        chooser = gtk.FileChooserDialog(title="Select a Delver Archive...",
                  action=gtk.FILE_CHOOSER_ACTION_OPEN,
                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                           gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            self.open_file(chooser.get_filename())

        chooser.destroy()
        #t = self.temporary_data.append(None, ["131","42 Items", "Image Data"])
        #self.temporary_data.append(t, ["8E31","12 kB","Something"])
        return None
    def menu_save_copy(self, widget, data=None):
        if not self.archive: 
            self.error_message("There is nothing to save.")
            return
        rv = self.ask_save_path()
        if not rv: return
        try:
            buf = self.archive.to_string()
            of = open(rv, 'wb')
            of.write(buf)
            of.close()
        except Exception,e:
            self.error_message("Unable to write '%s': %s"%(
                os.path.basename(self.opened_file), repr(e)))
            return
    def menu_save_as(self, widget, data=None):
        print "save as"
        if not self.archive: 
            self.error_message("There is nothing to save.")
            return
        rv = self.ask_save_path()
        if not rv: return
        self.opened_file = rv
        try:
            # The string is a buffer so we can overwrite in place.
            buf = self.archive.to_string()
            of = open(self.opened_file, 'wb')
            of.write(buf)
            of.close()
            self.set_saved()
        except Exception,e:
            self.error_message("Unable to write '%s': %s"%(
                os.path.basename(self.opened_file), repr(e)))
            return
        self.set_open_file(rv)
    def menu_save(self, widget, data=None):
        if not self.archive: 
            self.error_message("There is nothing to save.")
            return
        if not self.opened_file: self.opened_file = self.ask_save_path()
        if not self.opened_file: return
        try:
            # The string is a buffer so we can overwrite in place.
            buf = self.archive.to_string()
            of = open(self.opened_file, 'wb')
            of.write(buf)
            of.close()
            self.set_saved()
            print "Saved."
        except Exception,e:
            self.error_message("Unable to write '%s': %s"%(
                os.path.basename(self.opened_file), repr(e)))
            return
    def menu_export(self, widget, data=None):
        if not self.archive: 
            self.error_message("There is nothing to export.")
            return
        if not self.exported_directory: 
             self.exported_directory = self.ask_dir_path()
        if not self.exported_directory: return
        try:
            # The string is a buffer so we can overwrite in place.
            self.archive.to_path(self.exported_directory)
            self.set_saved()
        except Exception,e:
            self.error_message("Unable to export to '%s': %s"%(
                self.exported_directory, repr(e)))
            return
    def menu_export_as(self, widget, data=None):
        self.exported_directory = self.ask_dir_path()
        if not self.exported_directory: return
        try:
            # The string is a buffer so we can overwrite in place.
            self.archive.to_path(self.exported_directory)
            self.set_saved()
        except Exception,e:
            self.error_message("Unable to export to '%s': %s"%(
                self.exported_directory, repr(e)))
            return
    def menu_import(self, widget, data=None):
        if self.is_unsaved() and self.warn_unsaved_changes(): return
        self.exported_directory = self.ask_dir_path(gtk.STOCK_OPEN)
        if not self.exported_directory: return
        try:
            # The string is a buffer so we can overwrite in place.
            self.open_file(self.exported_directory)
            self.set_saved()
        except Exception,e:
            self.error_message("Unable to export to '%s': %s"%(
                self.exported_directory, repr(e)))
            return
        for recp in self.filechange: recp.signal_filechange()
        for recp in self.subindexchange: recp.signal_subindexchange()
        for recp in self.resourcechange: recp.signal_resourcechange()

    def menu_about(self, widget, data=None):
        if not self.aboutbox:
            self.aboutbox = gtk.Window(gtk.WINDOW_TOPLEVEL)
            self.aboutbox.set_title("About redelv")
            self.aboutbox.set_icon(
                gtk.gdk.pixbuf_new_from_file(images.icon_path))
            self.aboutbox.connect("delete_event", 
                (lambda *x: self.aboutbox.hide() or True))
            pbox = gtk.HBox(False,0)
            im = gtk.Image(); im.set_from_file(images.logo_path)
            pbox.pack_start(im,True,True,10)
            self.aboutbox.add(pbox)
            ab = gtk.Label(); ab.set_markup(ABOUT_TEXT)
            pbox.pack_start(ab,True,True,10)
        self.aboutbox.show_all()
            
    def menu_quit(self, widget, data=None):
        print "Quitting"
        if not self.delete_event(widget, None, data): self.destroy(None)
    def menu_get_info(self, widget, data=None):
        if not self.file_get_info_window:
             self.file_get_info_window = editgui.FileInfo(
                 self, gtk.WINDOW_TOPLEVEL)
        self.file_get_info_window.show_all()
    def menu_file_metadata(self, widget, data=None):
        if not self.file_metadata_window:
             self.file_metadata_window = editgui.FileMetadata(
                 self, gtk.WINDOW_TOPLEVEL)
        self.file_metadata_window.show_all()
    def menu_create_index(self, widget, data=None):
        return None
    def menu_delete(self, widget, data=None):
        print "Delete"
        return None
    def menu_duplicate(self, widget, data=None):
        if not self.current_resource_id: return
        askbox = AskNewResourceBox(self, 
            "Copy resource %04X to new ID:"%self.current_resource_id)
        #self.window.emit("filechange")
        choice = askbox.run() 
        new_resid = askbox.get_value()
        askbox.destroy()
        if not choice: return None
        data = self.archive.get(self.current_resource_id).get_data()

        res = self.archive.get(new_resid, create_new=True)
        res.set_data(data)
        self.tree_data.clear()
        self.archive.add_gui_tree()
        self.set_unsaved()
        

    def menu_create_resource(self, widget, data=None):
        askbox = AskNewResourceBox(self)
        #self.window.emit("filechange")
        choice = askbox.run() 
        new_resid = askbox.get_value()
        askbox.destroy()

        if not choice: return None
        
        res = self.archive.get(new_resid, create_new=True)
        res.set_data('\x00')
        self.tree_data.clear()
        self.archive.add_gui_tree()
        print "New resource", choice, new_resid, res
        self.set_unsaved()
        return None
    def menu_export_resource(self, widget, data=None):
        return None
    def menu_import_resource(self, widget, data=None):
        return None
    def menu_cut(self, widget, data=None):
        return None
    def menu_copy(self, widget, data=None):
        if self.current_resource:
            self.clipboard.set_text("Resource:%04X"%(self.current_resource_id))
        else:
            self.clipboard.set_text("Subindex:%d"%(self.current_subindex_id))
    def menu_paste(self, widget, data=None):
        return None
    def menu_select_base(self, widget, data=None):
        patch_base = self.ask_open_path(
            "Select patch basis (Unmodified scenario)")
        if not patch_base: return
        try:
            self.base_archive = delv.archive.Scenario(patch_base)
        except Exception, e:
            self.error_message("'%s' doesn't seem to be a valid archive: %s"%(
                os.path.basename(path), repr(e)))
            return
        self.patch_base = patch_base
        
    def menu_save_patch(self, widget, data=None):
        if not self.base_archive:
            self.error_message(
                "No patch basis is set. Select one using Patch:Select Base.")
            return
        if not self.archive:
            self.error_message(
                "Nothing open. Do File:Open to open a modified scenario file.")
            return
        if not self.patch_output_path: 
            self.patch_output_path = self.ask_save_path("Untitled Patch")
        if not self.patch_output_path: return
        newpatch = delv.archive.Patch()
        newpatch.patch_info(self.preferences['default_patch_info'])
        newpatch.diff(self.base_archive, self.archive)
        newpatch.to_path(self.patch_output_path)
        print "Saved patch with %d resources"%len(newpatch.resources())
        
    def menu_save_patch_as(self, widget, data=None):
        patch_output_path = self.ask_save_path("Untitled Patch")
        if not patch_output_path: return
        self.patch_output_path = patch_output_path
        self.menu_save_patch(self, widget, data)
    def menu_apply(self, widget, data=None):
        patch_path = self.ask_open_path("Select a Magpie or mag.py patch")
        if not patch_path: return
        try: 
            patch = delv.archive.Patch(patch_path)
        except Exception, e:
            self.error_message("'%s' doesn't seem to be a valid archive: %s"%(
                os.path.basename(patch_path), repr(e)))
            return
        if not patch.get(0xFFFF): 
            self.error_message("That archive contains no patch resource.")
            return
        patch.patch(self.archive)
        self.set_unsaved()
        self.refresh_tree()

        delv.archive.Patch(patch_path)
    def specific_ed(self, which="Hex"):
        if self.current_resource:
            editgui.editor_for_name(which)(
                self, self.current_resource,canonical=False).show_all()
        else:
            self.error_message("No resource is selected.")
    def open_editor(self, resid):
        ed = editgui.editor_for_resource(resid)(
                self,self.get_library().get_resource(resid))
        ed.show_all()
        return ed
    def menu_resource_editor(self, widget, data=None):
        if self.current_resource:
            #editgui.editor_for_subindex(self.current_subindex_id)(
            #    self, self.current_resource).show_all()
            editgui.editor_for_resource(self.current_resource.resid)(
                self,self.current_resource).show_all()
        else:
            self.error_message("No resource is selected.")
    #def menu_image_editor(self, *argv):
        
    def menu_hex_editor(self, widget, data=None):
        if not self.current_resource:
            self.error_message("No resource is selected.")
            return
        if self.current_resource_id in self.hex_editors_open:
            self.error_message(
                "Close the existing external editor for resid %04X first."%(
                     self.current_resource_id))
            return

        print "Using external hex editor", self.preferences['hex_editor_cmd']
        temp = tempfile.NamedTemporaryFile('w+b',
            prefix="redelv",
            suffix="resid%04X"%self.current_resource_id)
        temp.write(self.get_library().get_resource(
            self.current_resource_id).get_data())
        temp.flush()
        command = self.preferences['hex_editor_cmd']%temp.name
        self.tempfile_references[self.current_resource_id] = temp
        p=subprocess.Popen(command, shell=True)
        mtime = os.path.getmtime(temp.name)
        self.hex_editors_open[self.current_resource_id] = (p,temp,mtime)
        # turns out bless is a replacer rather than an overwriter...
        if self.timeout_sid is None:
            self.timeout_sid = gobject.timeout_add(300, self.file_mon_timer)
        #gfile =  gio.File(path=temp.name)
        #monitor =gfile.monitor_file(
        #    gio.FILE_MONITOR_NONE, None)
        #monitor = gfile.monitor_file()
        #monitor.connect("changed", self.hex_editor_changed, 
        #    (self.current_resource, temp,gfile))
        #self.specific_ed("Hex")
    def file_mon_timer(self):
        if not self.hex_editors_open:
            self.timeout_sid = None
            return False
        terminated = []
        for res,tfile in self.queued_changes:
            print "implemented queued change to", res.resid
            tfile = open(tfile.name,'r+b')
            res.set_data(tfile.read())
            self.get_library().purge_cache(res.resid)
            if self.hex_editors_open.has_key(res.resid):
                process, oldfile, mtime = self.hex_editors_open[res.resid]
                self.hex_editors_open[res.resid] = (process, tfile, 
                    os.path.getmtime(tfile.name))
            if self.preferences['instant_editor_propagation']:
                 # just be lazy, it's late
                 if self.open_editors.has_key(res.resid):
                     for editor in self.open_editors[res.resid]:
                         editor.revert()
        self.queued_changes = []
        for rid, (process, tempf, mtime) in self.hex_editors_open.items():
            if process.poll() is not None:
                terminated.append(rid)
                print "finished watching external editor for ", rid
                continue
            new_mtime = os.path.getmtime(tempf.name)
            if new_mtime != mtime:
                self.set_unsaved()
                print "external editor changed file", rid, mtime, new_mtime
                self.queued_changes.append((
                     self.get_library().get_resource(rid), tempf))
                self.hex_editors_open[rid] = (process, tempf, new_mtime)
        for rid in terminated: 
            del self.hex_editors_open[rid]
            del self.tempfile_references[rid]
        return True

    def signal_resource_saved(self, resid):
        if not self.hex_editors_open.has_key(resid):
            return
        print "Sending changes to an external editor for", resid
        process, tempf, mtime = self.hex_editors_open[resid]
        tempf.seek(0)
        tempf.write(self.library.get_resource(resid).get_data())
        tempf.flush()
        self.hex_editors_open[resid] = (
            process, tempf, os.path.getmtime(tempf.name))
    def menu_image_browser(self, widget, data=None):
        return None

    def menu_check_compatibility(self,widget,data=None):
        if not self.archive or not self.archive.get(0xFFFF):
            self.error_message("No patch is open; open one with File:Open.")
            return
        #other_patches = self.ask_multiple_files("Select one or more patches:")
        #if not other_patches: return
        #try:
        #    patches = [delv.archive.Patch(path) for path in other_patches]
        other_patch = self.ask_open_path("Select another patch:")
        if not other_patch: return
        try:
            patch = delv.archive.Patch(other_patch)
        except:
            self.error_message("Couldn't open that as a Delver Archive.")
            return
        if not patch.get(0xFFFF):
            self.error_message("That archive does not appear to be a patch.")
            return
        if patch.compatible(self.archive):
            self.info_message(
                "That patch appears to be compatible with the open patch.")
        else:
            self.info_message(
                "Incompatible: applying both patches may result in errors.")

            
    # stub
    def menu_(self, widget, data=None):
        return None

    def destroy(self, widget, data=None):
        gtk.main_quit()
    def delete_event(self, widget, event, data=None):
        if not self.is_unsaved(): return False
        return self.warn_unsaved_changes()

     # helpers
    def warn_unsaved_changes(self):
        dialog = gtk.MessageDialog(self.window, 
            gtk.DIALOG_MODAL , 
            gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            "This action will lose unsaved changes; are you sure?")
        rv= gtk.RESPONSE_YES != dialog.run()
        dialog.destroy()
        return rv
    def error_message(self, message):
        dialog = gtk.MessageDialog(self.window, 
            gtk.DIALOG_MODAL , 
            gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
            message)
        dialog.run()
        dialog.destroy()
    def info_message(self, message):
        dialog = gtk.MessageDialog(self.window, 
            gtk.DIALOG_MODAL , 
            gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
            message)
        dialog.run()
        dialog.destroy()
    def ask_dir_path(self,button=gtk.STOCK_SAVE):
        chooser = gtk.FileChooserDialog(
                  title="Select import/export directory...",
                  action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                           button,gtk.RESPONSE_OK))
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            rv =chooser.get_filename()
        else:
            rv = None
        chooser.destroy()
        return rv
    def ask_save_path(self, cname="Untitled Scenario"):
        chooser = gtk.FileChooserDialog(title="Select destination...",
                  action=gtk.FILE_CHOOSER_ACTION_SAVE,
                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                           gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        chooser.set_current_name(cname)
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            rv =chooser.get_filename()
        else:
            rv = None
        chooser.destroy()
        return rv
        
    def open_file(self, path,directory=False):
        self.tree_data = gtk.TreeStore(str,str,str,int,int)
        self.data_view.set_model(self.tree_data)
        try:
            self.archive = delv.archive.Scenario(path, 
                gui_treestore=self.tree_data)
            self.library = None
        except Exception, e:
            self.error_message("'%s' doesn't seem to be a valid archive: %s"%(
                os.path.basename(path), repr(e)))
            return
        if directory: self.set_open_directory(path)
        else: self.set_open_file(path)
    def set_open_directory(self,path):
        self.exported_directory = path
    def set_open_file(self,path):
        self.opened_file = path
        self.window.set_title(
            "redelv - %s"%(os.path.basename(path) if path else (
                 "[No File Open]")))
        for recp in self.filechange: recp.signal_filechange()
        for recp in self.subindexchange: recp.signal_subindexchange()
        for recp in self.resourcechange: recp.signal_resourcechange()
    def send_resourcechange(self):
        for recp in self.resourcechange: recp.signal_resourcechange()
    def get_library(self):
        try:
            if not self.library:
                self.library=delv.library.Library(self.underlay,self.archive) 
        except Exception,e:
            self.error_message(MSG_NO_UNDERLAY%repr(e))
        return self.library
    def register_editor(self, editor):
        if not self.open_editors.has_key(editor.res.resid):
            self.open_editors[editor.res.resid] = []
        self.open_editors[editor.res.resid].append(editor)
    def unregister_editor(self, editor):
        self.open_editors[editor.res.resid].remove(editor)
    def get_registered_editors(self, resid):
        return self.open_editors.get(resid, [])
