#BUB : Book Uploader Bot

* Author: Rohit Dua
* Hosted : [http://tools.wmflabs.org/bub](http://tools.wmflabs.org/bub)
* Email: 8ohit.dua AT gmail DOT com
* Originally created  to contribute to Wikimedia Commons(http://commons.wikimedia.org)

BUB is a web-tool built in Python that downloads books from public libraries like Google-Books, and then uploads them to the Internet Archive(http://archive.org) and Wikimedia Commons with the help of IA-Upload tool(http://tools.wmflabs.org/ia-upload/commons/init).  

## Components

The web-front code resides inside the /app directory, with the web templates inside the /app/templates subdirectory. The /digi_lib contains the modules associated with each public library. The /css, /images, /fonts folder contain the files required to run the web-frontend.

The bot code is inside /bot directory. worker.py and upload-checker.py run as continuous jobs.

## Contributing

Our code is maintained on [github](https://github.com/rohit-dua/BUB). We follow the same guidelines as the [mediawiki coding conventions](https://www.mediawiki.org/wiki/Manual:Coding_conventions/Python). 
For each public library, its associated module has to be present in /digi_lib and the config file should be set accordingly. Each new public-library module should contain the following functions-
verify_id(ID): Return 1 if ID is invalid. Return 2 if the book is not public-domain, return 3 for 404 errors else Return 0.
metadata(Id): Return dictionay of type:
```
{
 'image_url' : cover page URL,
 'printType' : book or magazine,
 'title' : book title,
 'subtitle' : book subtitle(if any),
 'author' : book author,
 'publisher' : book publisher,
 'publishedDate' : published date,
 'description' : book description,
 'infoLink' : hyperlink to book,
 'accessViewStatus' : Full View/Sample,
 'language' : book language
}
```
download_book(Id): Download book in pdf format save in file: gb_<library_id>_<Id>.pdf inside ./downloads/ folder.












