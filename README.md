#BUB : Book Uploader Bot

* Author: Rohit Dua
* Hosted : [http://tools.wmflabs.org/bub](http://tools.wmflabs.org/bub)
* Email: 8ohit.dua AT gmail DOT com
* Originally created  to contribute to Wikimedia Commons(http://commons.wikimedia.org)

BUB is a web-tool built in Python that downloads books from public libraries like Google-Books, and then uploads them to the Internet Archive(http://archive.org) and Wikimedia Commons with the help of IA-Upload tool(http://tools.wmflabs.org/ia-upload/commons/init).  

## Components

The core code resides inside the /app directory, with the web templates inside the /app/templates subdirectory. The /lib directory contains the necessary third party modules required to run the tool. While the /digi_lib contains the modules associated with each public library. The /css, /images, /fonts folder contain the files required to run the web-frontend.

## Contributing

Our code is maintained on [github](https://github.com/rohit-dua/BUB). We follow the same guidelines as the [mediawiki coding conventions](https://www.mediawiki.org/wiki/Manual:Coding_conventions/Python). 
For each public library, its associated module has to be present in /digi_lib and the config file should be set accordingly. Each new public-library module should contain the following functions-
verify_id(ID): Return 1 if ID is invalid. Return 10 if the book is not public-domain. else Return 0.
metadata(): Return dictionay of type:
```
{
 'image_url' : cover page URL,
 'title' : book title,
 'author' : book author,
 'publisher' : book publisher,
 'publishedDate' : published date,
 'description' : book description,
 'infoLink' : hyperlink to book
 'accessViewStatus' : Full View/Sample
}
```












