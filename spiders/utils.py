import re
import Levenshtein
from urlparse import urlsplit, urlunsplit, urljoin
from lxml import etree
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.selector import HtmlXPathSelector
from itertools import *

def extractLinks(response):
  """Extracts all href links of a page.

  @type  response: scrapy.http.Response
  @param response: the html page to process
  @rtype: generator of strings (itertools.imap)
  @return: all the href links of the page
  """
  return imap(lambda _: _.url, SgmlLinkExtractor().extract_links(response))

def extractRssLink(response):
  """Extracts all the RSS and ATOM feed links of a page.

  @type  response: scrapy.http.Response
  @param response: the html page to process
  @rtype: generator of strings (itertools.imap)
  @return: all the feed links of the page
  """
  parser = HtmlXPathSelector(response)
  paths = imap(lambda _: "//link[@type='{}']/@href".format(_), (
      "application/atom+xml",
      "application/atom",
      "text/atom+xml",
      "text/atom",
      "application/rss+xml",
      "application/rss",
      "text/rss+xml",
      "text/rss",
      "application/rdf+xml",
      "application/rdf",
      "text/rdf+xml",
      "text/rdf",
      "text/xml",
      "application/xml"))
  results = chain(*imap(lambda _: parser.select(_).extract(), paths))
  absoluts = imap(lambda _: urljoin(response.url, _), results)
  return absoluts
  
def xPathSelectFirst(response, query):
  """Executes a XPath query and return a string representation of the first
  result.

  @type  response: scrapy.http.Response
  @param response: the html page to process
  @type  query: string
  @param query: the XPath query to execute
  @rtype: string
  @return: the first result of the query, empty string if no result
  """
  return (HtmlXPathSelector(response).select(query).extract()
      or [""])[0] # .headOption.getOrElse("")

def bestXPathTo(string, html):
  """Computes the XPath query returning the node with closest string
  representation to a given string. Here are a few examples:
  
    >>> page = "<html><head><title>title</title></head><body><h1>post\
    ... </h1></body></html>"
    >>> bestXPathTo(u"a post", etree.HTML(page))
    '/html/body/h1'
    >>> complex = "<html><body><div>#1</div><div>#2<div><p>nested\
    ... </p></div></div></body></html>"
    >>> bestXPathTo(u"nested", etree.HTML(complex))
    '/html/body/div[2]/div/p'
  
  The U{Levenshtein<http://en.wikipedia.org/wiki/Levenshtein_distance>}
  distance is used to measure string similarity. The current implementation
  iterates over all the html nodes and computes the Levenshtein distance to
  the input node for each of them. In order to improve performance a first
  filtering phase using the node length and (possibly) the character
  occurrences could be used to reduce the calls to the expensive O(n^2)
  Levenshtein algorithm.
  
  @type  string: string
  @param string: the string to search in the document
  @type  html: lxml.etree._Element
  @param html: the html document tree where to search for the string
  @rtype: string
  @return: the XPath query that returns the node the most similar to string
  """
  # TODO fix for korben.info
  nodePaths = imap(lambda _: etree.ElementTree(html).getpath(_), html.iter())
  xPathEvaluator = lambda _: unicode(etree.tostring(html.xpath(_)[0]))
  ratio = lambda _: Levenshtein.ratio(xPathEvaluator(_), string)
  return max(nodePaths, key=ratio)

def pruneUrl(url):
  """Prunes a given url to extract only the essential information for
  duplicate detection purpose. Note that the returned string is not a valide
  url. Here are a few example prunings:
  
    >>> pruneUrl("https://mnmlist.com/havent/")
    '//mnmlist.com/havent'
    >>> pruneUrl("http://en.wikipedia.org/wiki/Pixies#Influences")
    '//en.wikipedia.org/wiki/pixies'
    >>> pruneUrl("http://WWW.W3SCHOOLS.COM/html/html_examples.asp")
    '//www.w3schools.com/html/html_examples'
  
  @type  url: string
  @param url: the url to prune
  @rtype: string
  @return: the pruned url
  """
  (scheme, netloc, path, query, fragment) = urlsplit(url)
  extensionRegex = ("(?i)\.(asp|aspx|cgi|exe|fcgi|fpl|htm|html|jsp|php|"
        + "php3|php4|php5|php6|phps|phtml|pl|py|shtm|shtml|wml)$")
  prunedPath = re.sub(extensionRegex, "", path.rstrip("/"))
  return urlunsplit((None, netloc, prunedPath, query, None)).lower()