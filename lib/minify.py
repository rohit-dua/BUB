#!/usr/bin/env python

import htmlmin
import cssmin

def minify(text):
    """Minify html and css part of text"""
    return cssmin.cssmin(htmlmin.minify( text, remove_comments = True))
