

## context
An object containing everything about an environment resolve. Contexts can be stored in
  .rxt files, and used to reconstruct the same environment at a later date.

## local package path
Path to package repository where locally-developed packages are installed to. This path typically
appears at the front of the packages search path. It is typically `~/packages`.

## package
A versioned piece of software - the things that rez manages.

## package commands
A block of python code in the package definition file that determines how the package updates the
environment it is used in.

## package definition file
A file, such as 'package.py', that defines everything we want to know about a package, including
its dependencies. Every package has one.

## package repository
A place where packages are stored - usually a directory on disk.

## package request
A string describing a request for a package, such as "python-2.6+", "foo==1.0.0".

## package search path
Search path that rez uses to find packages.

## request
A list of package requests, such as ("python-2.6+", "foo-1", "bah==2.3.3").

## resolve
A list of packages resulting from resolving a request with the dependency solver.

## rez-config
A command line tool that shows the current rez configuration settings.

## rez-env
A command line tool that places the user into a newly resolved environment.

## version
A version number, such as "1", "2.0", "1.5.3alpha".

## version conflict
Two requests for the same package that do not overlap. For example, ("python-2.5", "python-2.7").

## version range
A string describing a range of possible versions, such as "4+", "<2.1", "3.0", "1.1+<2", "==4.2.2".
