# BUB : Book Uploader Bot

* Author: Rohit Dua
* Hosted : [http://tools.wmflabs.org/bub](http://tools.wmflabs.org/bub)
* Email: 8ohit.dua AT gmail DOT com
* Originally created  to contribute to [Wikimedia Commons](http://commons.wikimedia.org) and [Internet Archive](http://archive.org)
* LICENSE : [GNU GENERAL PUBLIC LICENSE Version 3](http://tools.wmflabs.org/bub/license)

BUB is a web-tool built in Python that downloads books from public libraries like Google-Books, and then uploads them to the [Internet Archive](http://archive.org) and Wikimedia Commons with the help of [IA-Upload tool](http://tools.wmflabs.org/ia-upload/commons/init).  

## Currently supported libraries:

* Google-Books
* Brasiliana-USP
* DSpace-based-library
* HathiTrust
* Digital-Memory-of-Catalonia(mdc)
* Manual-Wildcard

## Components

The web-front code resides inside the /app directory. The /digi_lib contains the modules associated with each public library.
The bot code is inside /bot directory.

## Contributing

Our code is maintained on [github](https://github.com/rohit-dua/BUB). We follow the same guidelines as the [mediawiki coding conventions](https://www.mediawiki.org/wiki/Manual:Coding_conventions/Python). 
For each public library, its associated module has to be present in /digi_lib and the config file should be set accordingly.


