"""Content Extractor.

TODO: Use readability as a fallback
TODO: generate XPath for divs without class/id
"""
from bibcrawl.utils.ohpython import *
from bibcrawl.utils.parsing import parseHTML, extractFirst
from bibcrawl.utils.stringsimilarity import stringSimilarity
from feedparser import parse as feedparse # http://pythonhosted.org/feedparser/
from heapq import nlargest
from lxml import etree # http://lxml.de/index.html#documentation
from scrapy.exceptions import CloseSpider

class ContentExtractor(object):
  """Extracts the content of blog posts using a rss feed. Usage:

  >>> from urllib2 import urlopen
  >>> from bibcrawl.utils.parsing import parseHTML
  >>> from bibcrawl.units.mockserver import MockServer, dl
  >>> pages = ("korben.info/80-bonnes-pratiques-seo.html", "korben.info/app-"
  ... "gratuite-amazon.html", "korben.info/cest-la-rentree-2.html",
  ... "korben.info/super-parkour-bros.html")
  >>> with MockServer():
  ...   extractor = ContentExtractor(dl("korben.info/feed"))
  ...   extractor.feed(dl(pages[0]), "http://{}".format(pages[0]))
  ...   extractor.feed(dl(pages[1]), "http://{}".format(pages[1]))
  ...   extractor.feed(dl(pages[2]), "http://{}".format(pages[2]))
  ...   content = extractor(parseHTML(dl(pages[3])))
  Best XPaths are:
  //*[@class='post-content']
  //*[@class='post-title']
  >>> len(extractor.getRssLinks())
  30
  >>> 6000 < len(content[0]) < 6200
  True
  """

  def __init__(self, rss):
    """Instantiates a content extractor for a given rss feed.

    @type  rss: string
    @param rss: the rss/atom feed
    """
    self.rssEntries = feedparse(rss).entries
    self.rssLinks = tuple(imap(lambda _: _.link, self.rssEntries))
    self.urlZipPages = list()
    self.xPaths = None
    self.needsRefresh = True

  def getRssLinks(self):
    """Returns the post links extracted from the rss feed.

    @rtype: tuple of strings
    @return: the post links extracted from the rss feed
    """
    return self.rssLinks

  def feed(self, page, url):
    """Feeds the extractor with a new page. Careful, the urls feeded here must
    match one url found in the rss feed provided in the constructor.

    @type  page: string
    @param page: the html page feeded
    @type  url: string
    @param url: the url of the page, as found in the rss feed
    """
    self.needsRefresh = True
    self.urlZipPages.append((url, page))

  def __call__(self, parsedPage):
    """Extracts content from a page.

    @type  parsedPage: lxml.etree._Element
    @param parsedPage: the parsed page, computed for the default value None
    @rtype: 1-tuple of strings
    @return: the extracted (content, )
    """
    if self.needsRefresh:
      self._refresh()
    return tuple(imap(lambda _: extractFirst(parsedPage, _), self.xPaths))

  def _refresh(self):
    """Refreshes the XPaths with the current pages. Called internally once per
    feed+ __call__ sequence."""
    self.needsRefresh = False

    # Python is so bad at this... Here is (for documentation purpose) how it
    # would be written in Scala (with url/_1 and page/_2 if urlZipPages is a
    # list of pairs and not a list of case classes):
    # val pageUrls = urlZipPages.map(_.url)
    # val entries = rssEntries.filter(pageUrls contains _.link).sortBy(_.link)
    # val parsedPages = urlZipPages.filter(rssLinks contains _.url)
    #   .sortBy(_.url).map(parseHTML(_.page))
    pageUrls = tuple(imap(lambda (url, _): url, self.urlZipPages))
    entries = sorted(
        ifilter(lambda _: _.link in pageUrls, self.rssEntries),
        key=lambda _: _.link)
    parsedPages = tuple(imap(
        lambda (_, page): parseHTML(page),
        sorted(
          ifilter(lambda (url, _): url in self.rssLinks, self.urlZipPages),
          key=lambda (url, _): url)))
    extractors = (
        extractContent,
        lambda _: _.title,
        # updated, published_parsed, updated_parsed, links, title, author,
        # summary_detail, summary, content, guidislink, title_detail, href,
        # link, authors, thr_total, author_detail, id, tags, published
    )
    self.xPaths = tuple(imap(
        lambda extractr: bestPath(zip(imap(extractr, entries), parsedPages)),
        extractors))

    print("Best XPaths are:")
    print("\n".join(self.xPaths))

def extractContent(feed):
  try:
    return feed.content[0].value
  except AttributeError:
    # try:
    return feed.description
    # except AttributeError:
    #   # TODO: fallback
    #   raise CloseSpider("Feed entry has no content and no description")


def bestPath(contentZipPages):
  """Given a list of content/page, computes the best XPath query that would
  return the content on each page.

  @type  contentZipPages: list of pairs of string/lxml.etree._Element
  @param contentZipPages: the list of content/page used to guide the process
  @rtype: string
  @return: the XPath query that matches at best the content on each page
  """
  queries = set(nodeQueries(imap(lambda _: _[1], contentZipPages)))
  ratio = lambda content, page, query: (
      stringSimilarity(content, extractFirst(page, query)))
  # TODO: breaks if last post is a youtube video or a common short title..
  topQueriesForFirst = nlargest(6, queries, key=
      partial(ratio, *contentZipPages[0]))
  topQueries = tuple(imap(
      lambda (c, p): max(topQueriesForFirst, key=partial(ratio, c, p)),
      contentZipPages))

  # # DEBUG:
  # from pprint import pprint
  # for q in topQueriesForFirst:
  #   pprint(q)
  #   pprint(ratio(contentZipPages[0][0], contentZipPages[0][1], q))
  # from bibcrawl.utils.stringsimilarity import _cleanTags

  # for q in topQueriesForFirst:
  #   print ""
  #   pprint(q)
  #   pprint(_cleanTags(extractFirst(contentZipPages[0][1], q)))

  # print ""
  # print ""
  # pprint((_cleanTags(contentZipPages[0][0])))
  # # from bibcrawl.utils.stringsimilarity import _cleanTags
  # # # pprint(topQueriesForFirst)
  # # for q in list(topQueriesForFirst):
  # #   pprint(q)
  # #   pprint(_cleanTags(contentZipPages[0][0] or "dummy"))
  # #   pprint(_cleanTags(extractFirst(contentZipPages[0][1], q)))
  # #   print ""

  # # q = max(set(topQueries), key=topQueries.count)
  # # for c, p in contentZipPages:
  # #   print "..."
  # #   pprint(c)
  # #   pprint(extractFirst(p, q))
  # from time import sleep
  # sleep(100000)
  # # DEBUG..

  return max(set(topQueries), key=topQueries.count)

def nodeQueries(pages):
  """Compute queries to each node of the html page using per id/class global
  selection.

    >>> from lxml.etree import HTML
    >>> page = HTML("<h1 class='title'>#1</h1><div id='footer'>#2</div> [...]")
    >>> tuple( nodeQueries([page]) )
    ("//*[@class='title']", "//*[@id='footer']")

  @type  pages: collections.Iterable of lxml.etree._Element
  @param pages: the pages to process
  @rtype: generator of strings
  @return: the queries
  """
  for page in pages:
    for node in page.iter():
      for selector in ("id", "class"):
        attribute = node.get(selector)
        if attribute and not any(imap(lambda _: _.isdigit(), attribute)):
          yield "//*[@{}='{}']".format(selector, attribute)
          break
      else:
        pass # TODO path
