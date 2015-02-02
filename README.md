# delvmod
A Python module and demonstration programs for modding a classic computer RPG


WHAT IS delv FOR?

delv is a Python module that allows users to manipulate the archives of games
based on the "Delver" engine, written 1995-1999 by Glenn Andreas. It was only
used, as far as is known, in the 1999 game "Cythera," published by Ambrosia
Software, inc. 

Extensive technical documentation of this engine and game, which were used to
produce delv, can be found at http://www.ferazelhosting.net/wiki/Cythera

The wiki page for delv itself is http://www.ferazelhosting.net/wiki/delv


WHO WROTE delv AND HOW?

delv was originally written by Bryce Schroeder, bryce.schroeder@gmail.com

Website: http://www.bryce.pw

Prior work by various persons over the years and various technical information
published by the author of the engine have been used in the Technical 
Documentation Project supporting delv, but mainly the game has been documented
through meticulous black-box reverse engineering. For example, the graphics
format was successfully interpreted through systematic "mutation experiments"
on the graphics resources. (The notes run to about 40 pages of screenshots and
comments.) In other cases, simple observation has sufficed; for example, the
essentials of the Delver Archive format are almost immediately evident by 
inspection with a hex editor.

Cythera's license agreement does not appear to purport to forbid reverse 
engineering, and if it did, reverse engineering for interoperability is 
allowed in the United States and many other countries in any case. (delv is 
based heavily on the facilities offered by modern dynamic programming languages
and probably would not benefit much from the specific, highly optmized 
techniques of implementation that are likely used in Delver anyway.)


WHAT IS THE PURPOSE OF delv?

Self-evidently, you could use it to make a third-party RPG editor suite that is
interoperable with a Delver engine based game like Cythera. Another application
would, e.g. be map viewers or dynamic walkthrough/guide websites for the game.

WHAT CAN I DO WITH delv?
Anything permitted by the GPL version 3, but we ask you to please not attempt 
to use it to circumvent Cythera's shareware restrictions, and not to distribute
any modified versions of "Cythera Data" (i.e. the scenario file). This latter 
action at least would violate Ambrosia Software's copyright (and the Cythera 
EULA, as it permits only redistribution of the unmodified and complete game.)


HOW IS delv DOCUMENTED?

Most of the classes and methods have docstrings. An overview is presented here:

delv.archive - Reads and writes Delver Archives (e.g. "Cythera Data")

delv.colormap - Contains the palette of indexed colors used by Cythera. You 
probably won't need to access this directly.

delv.graphics - Handles the Delver Engine's custom compressed graphics format

delv.monster - Handles the special monster stats resource. (Note that in the
course of the game, the scripting system would normally access this itself
and interpret it without any special help; this module is provided for the 
convenience of editors. How monsters defined is, in principle, scenario
dependent.)

delv.script - Assembles, disassembles, and (in principle) executes scripts,
 including virtual machine scripts and AI-type scripts.

delv.sound - Handles sound and music resources.

delv.store - Utility functions for editing various kinds of binary storage
formats used by Delver, such as symbol lists and serialized scripting system
objects.

delv.tile - Handles graphical tiles and their renderer / engine properties 
(movement obstruction, vision blocking, light source specifications, etc.)

delv.util - Utilities for other delv modules, but you can use the public 
functions and classes if you like. 


GETTING AT SOUNDS AND GRAPHICS

Multimedia formats are provided in reasonably universal formats, e.g. arrays,
you will probably have to write glue code if you want to display them as PNG,
use them with pygame, or whatever. delv couldn't practically support all the
different ways of getting multimedia to the output device using python, and it
would introduce huge testing complexity and lots of dependencies for something
that is intended to also make simple command line tools and maybe even run in
a browser-based python implementation someday. Sorry about that.


FUTURE DIRECTIONS

As of the present, the scripting system's virtual machine has not been 
successfully reverse engineered and documented by the Technical Documentation 
Project. Therefore, the delv.script module remains unfinished and will likely 
remain so for some time. 

Features related to the creation of "Magpie"-type patches in delv.archive
remain unimplemented, pending complete documentation of the Magpie patch
format. (It is based on a delver archive, but the patch resource proper has
not been carefully investigated.)


