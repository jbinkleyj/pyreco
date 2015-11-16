__FILENAME__ = process_twitter
"""
Example for using langid.py to identify the language of messages
on a twitter livestream. Optionally, it can also filter messages
and display only those in a target language(s).

Expects a Twitterstream on STDIN, such as the one provided by:

# curl https://stream.twitter.com/1/statuses/sample.json -u<username> -s

Outputs lang:message one-per-line to STDOUT

Marco Lui, June 2012
"""

import sys
import langid
import json
import optparse

if __name__ == "__main__":
  parser = optparse.OptionParser()
  parser.add_option('-l', '--langs', dest='langs', help='comma-separated set of target ISO639 language codes (e.g en,de)')
  opts, args = parser.parse_args()

  lang_set = set(opts.langs.split(",")) if opts.langs else None

  try:
    for line in sys.stdin:
      j = json.loads(line)
      if j.get('retweet_count') == 0:
        text = j.get('text')
        if text:
          lang, conf = langid.classify(text)
          if lang_set is None or lang in lang_set:
            print "{0}: {1}".format(lang, text.encode('utf8'))
  except (IOError, KeyboardInterrupt):
    # Terminate on broken pipe or ^C
    pass


########NEW FILE########
__FILENAME__ = langid
#!/usr/bin/env python
"""
langid.py - 
Language Identifier by Marco Lui April 2011

Based on research by Marco Lui and Tim Baldwin.

Copyright 2011 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

# Defaults for inbuilt server
HOST = None #leave as none for auto-detect
PORT = 9008
FORCE_WSGIREF = False
NORM_PROBS = True # Normalize optput probabilities.

# NORM_PROBS can be set to False for a small speed increase. It does not
# affect the relative ordering of the predicted classes. 

import base64
import bz2
import json
import optparse
import logging
import numpy as np
from cPickle import loads
from wsgiref.simple_server import make_server
from wsgiref.util import shift_path_info
from urlparse import parse_qs
from collections import defaultdict

logger = logging.getLogger(__name__)

model="""
"""

# Convenience methods defined below will initialize this when first called.
identifier = None

def set_languages(langs=None):
  """
  Set the language set used by the global identifier.

  @param langs a list of language codes
  """
  global identifier
  if identifier is None:
    load_model()

  return identifier.set_languages(langs)


def classify(instance):
  """
  Convenience method using a global identifier instance with the default
  model included in langid.py. Identifies the language that a string is 
  written in.

  @param instance a text string. Unicode strings will automatically be utf8-encoded
  @returns a tuple of the most likely language and the confidence score
  """
  global identifier
  if identifier is None:
    load_model()

  return identifier.classify(instance)

def rank(instance):
  """
  Convenience method using a global identifier instance with the default
  model included in langid.py. Ranks all the languages in the model according
  to the likelihood that the string is written in each language.

  @param instance a text string. Unicode strings will automatically be utf8-encoded
  @returns a list of tuples language and the confidence score, in descending order
  """
  global identifier
  if identifier is None:
    load_model()

  return identifier.rank(instance)
  
def cl_path(path):
  """
  Convenience method using a global identifier instance with the default
  model included in langid.py. Identifies the language that the file at `path` is 
  written in.

  @param path path to file
  @returns a tuple of the most likely language and the confidence score
  """
  global identifier
  if identifier is None:
    load_model()

  return identifier.cl_path(path)

def rank_path(path):
  """
  Convenience method using a global identifier instance with the default
  model included in langid.py. Ranks all the languages in the model according
  to the likelihood that the file at `path` is written in each language.

  @param path path to file
  @returns a list of tuples language and the confidence score, in descending order
  """
  global identifier
  if identifier is None:
    load_model()

  return identifier.rank_path(path)

def load_model(path = None):
  """
  Convenience method to set the global identifier using a model at a
  specified path.

  @param path to model
  """
  global identifier
  logger.info('initializing identifier')
  if path is None:
    identifier = LanguageIdentifier.from_modelstring(model)
  else:
    identifier = LanguageIdentifier.from_modelpath(path)

class LanguageIdentifier(object):
  """
  This class implements the actual language identifier.
  """

  @classmethod
  def from_modelstring(cls, string, *args, **kwargs):
    model = loads(bz2.decompress(base64.b64decode(string)))
    nb_ptc, nb_pc, nb_classes, tk_nextmove, tk_output = model
    nb_numfeats = len(nb_ptc) / len(nb_pc)

    # reconstruct pc and ptc
    nb_pc = np.array(nb_pc)
    nb_ptc = np.array(nb_ptc).reshape(len(nb_ptc)/len(nb_pc), len(nb_pc))
   
    return cls(nb_ptc, nb_pc, nb_numfeats, nb_classes, tk_nextmove, tk_output, *args, **kwargs)

  @classmethod
  def from_modelpath(cls, path, *args, **kwargs):
    with open(path) as f:
      return cls.from_modelstring(f.read(), *args, **kwargs)

  def __init__(self, nb_ptc, nb_pc, nb_numfeats, nb_classes, tk_nextmove, tk_output,
               norm_probs = NORM_PROBS):
    self.nb_ptc = nb_ptc
    self.nb_pc = nb_pc
    self.nb_numfeats = nb_numfeats
    self.nb_classes = nb_classes
    self.tk_nextmove = tk_nextmove
    self.tk_output = tk_output

    if norm_probs:
      def norm_probs(pd):
        """
        Renormalize log-probs into a proper distribution (sum 1)
        The technique for dealing with underflow is described in
        http://jblevins.org/log/log-sum-exp
        """
        # Ignore overflow when computing the exponential. Large values
        # in the exp produce a result of inf, which does not affect
        # the correctness of the calculation (as 1/x->0 as x->inf). 
        # On Linux this does not actually trigger a warning, but on 
        # Windows this causes a RuntimeWarning, so we explicitly 
        # suppress it.
        with np.errstate(over='ignore'):
          pd = (1/np.exp(pd[None,:] - pd[:,None]).sum(1))
        return pd
    else:
      def norm_probs(pd):
        return pd

    self.norm_probs = norm_probs

    # Maintain a reference to the full model, in case we change our language set
    # multiple times.
    self.__full_model = nb_ptc, nb_pc, nb_classes

  def set_languages(self, langs=None):
    logger.debug("restricting languages to: %s", langs)

    # Unpack the full original model. This is needed in case the language set
    # has been previously trimmed, and the new set is not a subset of the current
    # set.
    nb_ptc, nb_pc, nb_classes = self.__full_model

    if langs is None:
      self.nb_classes = nb_classes 
      self.nb_ptc = nb_ptc
      self.nb_pc = nb_pc

    else:
      # We were passed a restricted set of languages. Trim the arrays accordingly
      # to speed up processing.
      for lang in langs:
        if lang not in nb_classes:
          raise ValueError, "Unknown language code %s" % lang

      subset_mask = np.fromiter((l in langs for l in nb_classes), dtype=bool)
      self.nb_classes = [ c for c in nb_classes if c in langs ]
      self.nb_ptc = nb_ptc[:,subset_mask]
      self.nb_pc = nb_pc[subset_mask]

  def instance2fv(self, text):
    """
    Map an instance into the feature space of the trained model.
    """
    if isinstance(text, unicode):
      text = text.encode('utf8')

    arr = np.zeros((self.nb_numfeats,), dtype='uint32')

    # Convert the text to a sequence of ascii values
    ords = map(ord, text)

    # Count the number of times we enter each state
    state = 0
    statecount = defaultdict(int)
    for letter in ords:
      state = self.tk_nextmove[(state << 8) + letter]
      statecount[state] += 1

    # Update all the productions corresponding to the state
    for state in statecount:
      for index in self.tk_output.get(state, []):
        arr[index] += statecount[state]

    return arr

  def nb_classprobs(self, fv):
    # compute the partial log-probability of the document given each class
    pdc = np.dot(fv,self.nb_ptc)
    # compute the partial log-probability of the document in each class
    pd = pdc + self.nb_pc
    return pd

  def classify(self, text):
    """
    Classify an instance.
    """
    fv = self.instance2fv(text)
    probs = self.norm_probs(self.nb_classprobs(fv))
    cl = np.argmax(probs)
    conf = float(probs[cl])
    pred = str(self.nb_classes[cl])
    return pred, conf

  def rank(self, text):
    """
    Return a list of languages in order of likelihood.
    """
    fv = self.instance2fv(text)
    probs = self.norm_probs(self.nb_classprobs(fv))
    return [(str(k),float(v)) for (v,k) in sorted(zip(probs, self.nb_classes), reverse=True)]

  def cl_path(self, path):
    """
    Classify a file at a given path
    """
    with open(path) as f:
      retval = self.classify(f.read())
    return path, retval

  def rank_path(self, path):
    """
    Class ranking for a file at a given path
    """
    with open(path) as f:
      retval = self.rank(f.read())
    return path, retval
      

# Based on http://www.ubacoda.com/index.php?p=8
query_form = """
<html>
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8">
    <title>Language Identifier</title>
    <script src="//ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js" type="text/javascript"></script>
    <script type="text/javascript" charset="utf-8">
      $(document).ready(function() {{
        $("#typerArea").keyup(displayType);
      
        function displayType(){{
          var contents = $("#typerArea").val();
          if (contents.length != 0) {{
            $.post(
              "/rank",
              {{q:contents}},
              function(data){{
                for(i=0;i<5;i++) {{
                  $("#lang"+i).html(data.responseData[i][0]);
                  $("#conf"+i).html(data.responseData[i][1]);
                }}
                $("#rankTable").show();
              }},
              "json"
            );
          }}
          else {{
            $("#rankTable").hide();
          }}
        }}
        $("#manualSubmit").remove();
        $("#rankTable").hide();
      }});
    </script>
  </head>
  <body>
    <form method=post>
      <center><table>
        <tr>
          <td>
            <textarea name="q" id="typerArea" cols=40 rows=6></textarea></br>
          </td>
        </tr>
        <tr>
          <td>
            <table id="rankTable">
              <tr>
                <td id="lang0">
                  <p>Unable to load jQuery, live update disabled.</p>
                </td><td id="conf0"/>
              </tr>
              <tr><td id="lang1"/><td id="conf1"></tr>
              <tr><td id="lang2"/><td id="conf2"></tr>
              <tr><td id="lang3"/><td id="conf3"></tr>
              <tr><td id="lang4"/><td id="conf4"></tr>
            </table>
            <input type=submit id="manualSubmit" value="submit">
          </td>
        </tr>
      </table></center>
    </form>

  </body>
</html>
"""
def application(environ, start_response):
  """
  WSGI-compatible langid web service.
  """
  try:
    path = shift_path_info(environ)
  except IndexError:
    # Catch shift_path_info's failure to handle empty paths properly
    path = ''

  if path == 'detect' or path == 'rank':
    data = None

    # Extract the data component from different access methods
    if environ['REQUEST_METHOD'] == 'PUT':
      data = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
    elif environ['REQUEST_METHOD'] == 'GET':
      try:
        data = parse_qs(environ['QUERY_STRING'])['q'][0]
      except KeyError:
        # No query, provide a null response.
        status = '200 OK' # HTTP Status
        response = {
          'responseData': None,
          'responseStatus': 200, 
          'responseDetails': None,
        }
    elif environ['REQUEST_METHOD'] == 'POST':
      input_string = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
      try:
        data = parse_qs(input_string)['q'][0]
      except KeyError:
        # No key 'q', process the whole input instead
        data = input_string
    else:
      # Unsupported method
      status = '405 Method Not Allowed' # HTTP Status
      response = { 
        'responseData': None, 
        'responseStatus': 405, 
        'responseDetails': '%s not allowed' % environ['REQUEST_METHOD'] 
      }

    if data is not None:
      if path == 'detect':
        pred,conf = classify(data)
        responseData = {'language':pred, 'confidence':conf}
      elif path == 'rank':
        responseData = rank(data)

      status = '200 OK' # HTTP Status
      response = {
        'responseData': responseData,
        'responseStatus': 200, 
        'responseDetails': None,
      }
  elif path == 'demo':
    status = '200 OK' # HTTP Status
    headers = [('Content-type', 'text/html; charset=utf-8')] # HTTP Headers
    start_response(status, headers)
    return [query_form.format(**environ)]
    
  else:
    # Incorrect URL
    status = '404 Not Found'
    response = {'responseData': None, 'responseStatus':404, 'responseDetails':'Not found'}

  headers = [('Content-type', 'text/javascript; charset=utf-8')] # HTTP Headers
  start_response(status, headers)
  return [json.dumps(response)]

def main():
  global identifier

  parser = optparse.OptionParser()
  parser.add_option('-s','--serve',action='store_true', default=False, dest='serve', help='launch web service')
  parser.add_option('--host', default=HOST, dest='host', help='host/ip to bind to')
  parser.add_option('--port', default=PORT, dest='port', help='port to listen on')
  parser.add_option('-v', action='count', dest='verbosity', help='increase verbosity (repeat for greater effect)')
  parser.add_option('-m', dest='model', help='load model from file')
  parser.add_option('-l', '--langs', dest='langs', help='comma-separated set of target ISO639 language codes (e.g en,de)')
  parser.add_option('-r', '--remote',action="store_true", default=False, help='auto-detect IP address for remote access')
  parser.add_option('-b', '--batch', action="store_true", default=False, help='specify a list of files on the command line')
  parser.add_option('--demo',action="store_true", default=False, help='launch an in-browser demo application')
  parser.add_option('-d', '--dist', action='store_true', default=False, help='show full distribution over languages')
  parser.add_option('-u', '--url', help='langid of URL')
  parser.add_option('--line', action="store_true", default=False, help='process pipes line-by-line rather than as a document')
  parser.add_option('-n', '--normalize', action='store_true', default=False, help='normalize confidence scores to probability values')
  options, args = parser.parse_args()

  if options.verbosity:
    logging.basicConfig(level=max((5-options.verbosity)*10, 0))
  else:
    logging.basicConfig()

  if options.batch and options.serve:
    parser.error("cannot specify both batch and serve at the same time")

  # unpack a model 
  if options.model:
    try:
      identifier = LanguageIdentifier.from_modelpath(options.model, norm_probs = options.normalize)
      logger.info("Using external model: %s", options.model)
    except IOError, e:
      logger.warning("Failed to load %s: %s" % (options.model,e))
  
  if identifier is None:
    identifier = LanguageIdentifier.from_modelstring(model, norm_probs = options.normalize)
    logger.info("Using internal model")

  if options.langs:
    langs = options.langs.split(",")
    identifier.set_languages(langs)

  def _process(text):
    """
    Set up a local function to do output, configured according to our settings.
    """
    if options.dist:
      payload = identifier.rank(text)
    else:
      payload = identifier.classify(text)

    return payload


  if options.url:
    import urllib2
    import contextlib
    with contextlib.closing(urllib2.urlopen(options.url)) as url:
      text = url.read()
      output = _process(text)
      print options.url, len(text), output
    
  elif options.serve or options.demo:
    # from http://stackoverflow.com/questions/166506/finding-local-ip-addresses-in-python
    if options.remote and options.host is None:
      # resolve the external ip address
      import socket
      s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      s.connect(("google.com",80))
      hostname = s.getsockname()[0]
    elif options.host is None:
      # resolve the local hostname
      import socket
      hostname = socket.gethostbyname(socket.gethostname())
    else:
      hostname = options.host

    if options.demo:
      import webbrowser
      webbrowser.open('http://{0}:{1}/demo'.format(hostname, options.port))
    try:
      if FORCE_WSGIREF: raise ImportError
      # Use fapws3 if available
      import fapws._evwsgi as evwsgi
      from fapws import base
      evwsgi.start(hostname,str(options.port))
      evwsgi.set_base_module(base)
      evwsgi.wsgi_cb(('', application))
      evwsgi.set_debug(0)
      evwsgi.run()
    except ImportError:
      print "Listening on %s:%d" % (hostname, int(options.port))
      print "Press Ctrl+C to exit"
      httpd = make_server(hostname, int(options.port), application)
      try:
        httpd.serve_forever()
      except KeyboardInterrupt:
        pass
  elif options.batch:
    # Start in batch mode - interpret input as paths rather than content
    # to classify.
    import sys, os, csv
    import multiprocessing as mp

    def generate_paths():
      if len(args) > 0:
        paths = args
      else:
        from itertools import imap
        paths = map(str.strip,sys.stdin)

      for path in paths:
        if path:
          if os.path.isfile(path):
            yield path
          else:
            # No such path
            pass

    writer = csv.writer(sys.stdout)
    pool = mp.Pool()
    if options.dist:
      writer.writerow(['path']+identifier.nb_classes)
      for path, ranking in pool.imap_unordered(rank_path, generate_paths()):
        ranking = dict(ranking)
        row = [path] + [ranking[c] for c in identifier.nb_classes]
        writer.writerow(row)
    else:
      for path, (lang,conf) in pool.imap_unordered(cl_path, generate_paths()):
        writer.writerow((path, lang, conf))
  else:
    import sys
    if sys.stdin.isatty():
      # Interactive mode
      while True:
        try:
          print ">>>",
          text = raw_input()
        except Exception:
          break
        print _process(text)
    else:
      # Redirected
      if options.line:
        for line in sys.stdin.readlines():
          print _process(line)
      else:
        print _process(sys.stdin.read())
     

if __name__ == "__main__":
  main()

########NEW FILE########
__FILENAME__ = featWeights
"""
Tabulate feature weight data into a single CSV for
further analysis using other tools. This produces
a CSV with header. The features themselves are not
included.

Marco Lui, February 2013
"""

import argparse, os, csv, sys
import numpy as np
import bz2, base64
from cPickle import loads

from langid.train.common import read_weights, read_features

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('model', metavar="MODEL_DIR", help="path to langid.py training model dir")
  parser.add_argument('output', metavar="OUTPUT", help = "write to OUTPUT")
  parser.add_argument('-f','--features', metavar="FILE", help = 'only output features from FILE')
  parser.add_argument('--raw', action='store_true', help="include raw features")
  parser.add_argument('--bin', action='store_true', help="include ig for lang-bin")
  args = parser.parse_args()

  def model_file(name):
    return os.path.join(args.model, name)

  # Try to determine the set of features to consider
  if args.features:
    # Use a pre-determined feature list
    print >>sys.stderr,  "using user-supplied feature list:", args.features
    feats = read_features(args.features)
  elif os.path.exists(model_file('LDfeats')):
    # Use LDfeats
    print >>sys.stderr,  "using LDfeats"
    feats = read_features(model_file('LDfeats'))
  else:
    raise ValueError("no suitable feature list")

  print >>sys.stderr, "considering {0} features".format(len(feats))

  records = dict( (k, {}) for k in feats )
  headers = []

  headers.append('len')
  for k in feats:
    records[k]['len'] = len(k)


  # Document Frequency
  if os.path.exists(model_file('DF_all')):
    print >>sys.stderr, "found weights for document frequency"
    w = read_weights(model_file('DF_all'))
    headers.append('DF')
    for k in feats:
      records[k]['DF'] = w[k][0]

  # IG weights for the all-languages event
  if os.path.exists(model_file('IGweights.lang')):
    print >>sys.stderr, "found weights for lang"
    w = read_weights(model_file('IGweights.lang'))
    headers.append('IGlang')
    for k in feats:
      records[k]['IGlang'] = w[k][0]

  # IG weights for the all-domains event
  if os.path.exists(model_file('IGweights.domain')):
    print >>sys.stderr, "found weights for domain"
    w = read_weights(model_file('IGweights.domain'))
    headers.append('IGdomain')
    for k in feats:
      records[k]['IGdomain'] = w[k][0]

  # IG weights for language-binarized
  if args.bin and os.path.exists(model_file('IGweights.lang.bin')) and os.path.exists(model_file('lang_index')):
    print >>sys.stderr, "found weights for lang.bin"
    w = read_weights(model_file('IGweights.lang.bin'))

    # find the list of langs in-order
    with open(os.path.join(args.model, "lang_index")) as f:
      reader = csv.reader(f)
      langs = zip(*reader)[0]

    r_h = ['IGlang.bin.{0}'.format(l) for l in langs]
    headers.extend( r_h )
    for k in feats:
      records[k].update( dict(zip(r_h, w[k])) )
        
  if os.path.exists(model_file('LDfeats.scanner')) and os.path.exists(model_file('model')):
    print >>sys.stderr, "found weights for P(t|c)"
    with open(model_file('model')) as f:
      model = loads(bz2.decompress(base64.b64decode(f.read())))
    with open(model_file('LDfeats.scanner')) as f:
      _, _, nb_feats = loads(f.read())
    nb_ptc, nb_pc, nb_classes, tk_nextmove, tk_output = model
    nb_numfeats = len(nb_ptc) / len(nb_pc)
    nb_ptc = np.array(nb_ptc).reshape(len(nb_ptc)/len(nb_pc), len(nb_pc))

    # Normalize to 1 on the term axis
    for i in range(nb_ptc.shape[1]):
      nb_ptc[:,i] = (1/np.exp(nb_ptc[:,i][None,:] - nb_ptc[:,i][:,None]).sum(1))
    w = dict(zip(nb_feats, nb_ptc))

    r_h = ['ptc.{0}'.format(l) for l in nb_classes]
    headers.extend( r_h )
    for k in feats:
      records[k].update( dict(zip(r_h, w[k])) )

  if args.raw:
    headers.append('feat')
    for k in feats:
      records[k]['feat'] = k



  print >>sys.stderr, "writing output"
  with open(args.output, 'w') as f:
    writer = csv.DictWriter(f,headers)
    writer.writeheader()
    writer.writerows(records.values())
  
  print >>sys.stderr, "done"

########NEW FILE########
__FILENAME__ = printfeats
"""
Print features out in order of their weights

Marco Lui, November 2013
"""

import argparse, os, csv, sys

from langid.train.common import read_weights

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('file', help="file to read")
  parser.add_argument('-c','--column',help="project a specific column", type=int)
  parser.add_argument('-n','--number',help="output top N features", type=int)
  parser.add_argument('-v','--value',help="output the value used for ranking", action="store_true")
  parser.add_argument('--output', "-o", default=sys.stdout, type=argparse.FileType('w'), help = "write to OUTPUT")
  args = parser.parse_args()

  w = read_weights(args.file)
  n = args.number if args.number is not None else len(w)

  if args.column is not None:
    for key in sorted(w, key=lambda x:w[x][args.column], reverse=True)[:n]:
      if args.value:
        args.output.write("{0},{1}\n".format(repr(key),w[key][args.column]))
      else:
        args.output.write("{0}\n".format(repr(key)))
  else:
    for key in sorted(w, key=w.get, reverse=True)[:n]:
      if args.value:
        args.output.write("{0},{1}\n".format(repr(key),w[key]))
      else:
        args.output.write("{0}\n".format(repr(key)))


########NEW FILE########
__FILENAME__ = BLweight
"""
Implementing the "blacklist" feature weighting metric proposed by
Tiedemann & Ljubesic.

Marco Lui, February 2013
"""

NUM_BUCKETS = 64 # number of buckets to use in k-v pair generation
CHUNKSIZE = 50 # maximum size of chunk (number of files tokenized - less = less memory use)

import os
import argparse
import numpy as np

from common import read_features, makedir, write_weights
from scanner import build_scanner
from index import CorpusIndexer
from NBtrain import generate_cm, learn_pc, learn_ptc


if __name__ == "__main__":

  parser = argparse.ArgumentParser()
  parser.add_argument("-o","--output", metavar="DIR", help = "write weights to DIR")
  parser.add_argument('-f','--features', metavar="FILE", help = 'only output features from FILE')
  parser.add_argument("-t", "--temp", metavar='TEMP_DIR', help="store buckets in TEMP_DIR instead of in MODEL_DIR/buckets")
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-m","--model", help="save output to MODEL_DIR", metavar="MODEL_DIR")
  parser.add_argument("--buckets", type=int, metavar='N', help="distribute features into N buckets", default=NUM_BUCKETS)
  parser.add_argument("--chunksize", type=int, help="max chunk size (number of files to tokenize at a time - smaller should reduce memory use)", default=CHUNKSIZE)
  parser.add_argument("--no_norm", default=False, action="store_true", help="do not normalize difference in p(t|C) by sum p(t|C)")
  parser.add_argument("corpus", help="read corpus from CORPUS_DIR", metavar="CORPUS_DIR")
  parser.add_argument("pairs", metavar='LANG_PAIR', nargs="*", help="language pairs to compute BL weights for")
  args = parser.parse_args()

  # Work out where our model directory is
  corpus_name = os.path.basename(args.corpus)
  if args.model:
    model_dir = args.model
  else:
    model_dir = os.path.join('.', corpus_name+'.model')

  def m_path(name):
    return os.path.join(model_dir, name)

  # Try to determine the set of features to consider
  if args.features:
    # Use a pre-determined feature list
    feat_path = args.features
  elif os.path.exists(m_path('DFfeats')):
    # Use LDfeats
    feat_path = m_path('DFfeats')
  else:
    raise ValueError("no suitable feature list")

  # Where temp files go
  if args.temp:
    buckets_dir = args.temp
  else:
    buckets_dir = m_path('buckets')
  makedir(buckets_dir)

  all_langs = set()
  pairs = []
  for p in args.pairs:
    try:
      lang1, lang2 = p.split(',')
    except ValueError:
      # Did not unpack to two values
      parser.error("{0} is not a lang-pair".format(p))
    all_langs.add(lang1)
    all_langs.add(lang2)
    pairs.append((lang1, lang2))

  if args.output:
    makedir(args.output)
    out_dir = args.output
  else:
    out_dir = model_dir

  langs = sorted(all_langs)

  # display paths
  print "languages({1}): {0}".format(langs, len(langs))
  print "model path:", model_dir
  print "feature path:", feat_path
  print "output path:", out_dir
  print "temp (buckets) path:", buckets_dir

  feats = read_features(feat_path)

  indexer = CorpusIndexer(args.corpus, langs = langs)
  items = [ (d,l,p) for (d,l,n,p) in indexer.items ]
  if len(items) == 0:
    raise ValueError("found no files!")

  print "will process {0} features across {1} paths".format(len(feats), len(items))

  # produce a scanner over all the features
  tk_nextmove, tk_output = build_scanner(feats)

  # Generate a class map over all the languages we are dealing with
  cm = generate_cm([ (l,p) for d,l,p in items], len(langs))

  # Compute P(t|C)
  print "learning P(t|C)"
  paths = zip(*items)[2]
  nb_ptc = learn_ptc(paths, tk_nextmove, tk_output, cm, buckets_dir, args)
  nb_ptc = np.array(nb_ptc).reshape(len(feats), len(langs))

  # Normalize to 1 on the term axis
  print "renormalizing P(t|C)"
  for i in range(nb_ptc.shape[1]):
    # had to de-vectorize this due to memory consumption
    newval = np.empty_like(nb_ptc[:,i])
    for j in range(newval.shape[0]):
      newval[j] = (1/np.exp(nb_ptc[:,i] - nb_ptc[j,i]).sum())
    nb_ptc[:,i] = newval
    assert (1.0 - newval.sum()) < 0.0001

  print "doing per-pair output"
  for lang1, lang2 in pairs:
    # Where to do output
    if args.no_norm:
      weights_path = os.path.join(out_dir, ('BLfeats.no_norm.{0}.{1}'.format(lang1, lang2)))
    else:
      weights_path = os.path.join(out_dir, ('BLfeats.{0}.{1}'.format(lang1, lang2)))

    i1 = indexer.lang_index[lang1]
    i2 = indexer.lang_index[lang2]

    w = dict(zip(feats, np.abs((nb_ptc[:,i1] - nb_ptc[:,i2]) / (nb_ptc.sum(1) if not args.no_norm else 1))))
    write_weights(w, weights_path)
    print "wrote weights to {0}".format(weights_path)

########NEW FILE########
__FILENAME__ = common
"""
Common functions

Marco Lui, January 2013
"""

from itertools import islice
import marshal
import tempfile
import gzip

class Enumerator(object):
  """
  Enumerator object. Returns a larger number each call. 
  Can be used with defaultdict to enumerate a sequence of items.
  """
  def __init__(self, start=0):
    self.n = start

  def __call__(self):
    retval = self.n
    self.n += 1
    return retval

def chunk(seq, chunksize):
  """
  Break a sequence into chunks not exceeeding a predetermined size
  """
  seq_iter = iter(seq)
  while True:
    chunk = tuple(islice(seq_iter, chunksize))
    if not chunk: break
    yield chunk

def unmarshal_iter(path):
  """
  Open a given path and yield an iterator over items unmarshalled from it.
  """
  with gzip.open(path, 'rb') as f, tempfile.TemporaryFile() as t:
    t.write(f.read())
    t.seek(0)
    while True:
      try:
        yield marshal.load(t)
      except EOFError:
        break

import os, errno
def makedir(path):
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise

import csv
def write_weights(weights, path, sort_by_weight=False):
  w = dict(weights)
  with open(path, 'w') as f:
    writer = csv.writer(f)
    if sort_by_weight:
      try:
        key_order = sorted(w, key=w.get, reverse=True)
      except ValueError:
        # Could not order keys by value, value is probably a vector.
        # Order keys alphabetically in this case.
        key_order = sorted(w)
    else:
      key_order = sorted(w)

    for k in key_order:
      row = [repr(k)]
      try:
        row.extend(w[k])
      except TypeError:
        row.append(w[k])
      writer.writerow(row)

import numpy
def read_weights(path):
  with open(path) as f:
    reader = csv.reader(f)
    retval = dict()
    for row in reader:
      key = eval(row[0])
      #val = numpy.array( map(float,row[1:]) )
      val = numpy.array( [float(v) if v != 'nan' else 0. for v in row[1:]] )
      retval[key] = val
  return retval

def read_features(path):
  """
  Read a list of features in feature-per-line format, where each
  feature is a repr and needs to be evaled.
  @param path path to read from
  """
  with open(path) as f:
    return map(eval, f)

def write_features(features, path):
  """
  Write a list of features to a file at `path`. The repr of each
  feature is written on a new line.
  @param features list of features to write
  @param path path to write to
  """
  with open(path,'w') as f:
    for feat in features:
      print >>f, repr(feat)


def index(seq):
  """
  Build an index for a sequence of items. Assumes
  that the items in the sequence are unique.
  @param seq the sequence to index
  @returns a dictionary from item to position in the sequence
  """
  return dict((k,v) for (v,k) in enumerate(seq))

      

from itertools import imap
from contextlib import contextmanager, closing
import multiprocessing as mp

@contextmanager
def MapPool(processes=None, initializer=None, initargs=None, maxtasksperchild=None, chunksize=1):
  """
  Contextmanager to express the common pattern of not using multiprocessing if
  only 1 job is allocated (for example for debugging reasons)
  """
  if processes is None:
    processes = mp.cpu_count() + 4

  if processes > 1:
    with closing( mp.Pool(processes, initializer, initargs, maxtasksperchild)) as pool:
      f = lambda fn, chunks: pool.imap_unordered(fn, chunks, chunksize=chunksize)
      yield f
  else:
    if initializer is not None:
      initializer(*initargs)
    f = imap
    yield f

  if processes > 1:
    pool.join()

########NEW FILE########
__FILENAME__ = DFfeatureselect
#!/usr/bin/env python
"""
DFfeatureselect.py - 
First step in the LD feature selection process, select features based on document
frequency.

Marco Lui January 2013

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

######
# Default values
# Can be overriden with command-line options
######
MAX_NGRAM_ORDER = 4 # largest order of n-grams to consider
TOKENS_PER_ORDER = 15000 # number of tokens to consider for each order

import os, sys, argparse
import collections
import csv
import shutil
import tempfile
import marshal
import random
import numpy
import cPickle
import multiprocessing as mp
import atexit
import gzip
from itertools import tee, imap, islice
from collections import defaultdict
from datetime import datetime
from contextlib import closing

from common import Enumerator, unmarshal_iter, MapPool, write_features, write_weights

def pass_sum_df(bucket):
  """
  Compute document frequency (df) by summing up (key,domain,count) triplets
  over all domains.
  """
  doc_count = defaultdict(int)
  count = 0
  with gzip.open(os.path.join(bucket, "docfreq"),'wb') as docfreq:
    for path in os.listdir(bucket):
      # We use the domain buckets as there are usually less domains
      if path.endswith('.domain'):
        for key, _, value in unmarshal_iter(os.path.join(bucket,path)):
          doc_count[key] += value
          count += 1
    
    for item in doc_count.iteritems():
      docfreq.write(marshal.dumps(item))
  return count

def tally(bucketlist, jobs=None):
  """
  Sum up the counts for each feature across all buckets. This
  builds a full mapping of feature->count. This is stored in-memory
  and thus could be an issue for large feature sets.
  """

  with MapPool(jobs) as f:
    pass_sum_df_out = f(pass_sum_df, bucketlist)

    for i, keycount in enumerate(pass_sum_df_out):
      print "processed bucket (%d/%d) [%d keys]" % (i+1, len(bucketlist), keycount)

  # build the global term->df mapping
  doc_count = {}
  for bucket in bucketlist:
    for key, value in unmarshal_iter(os.path.join(bucket, 'docfreq')):
      doc_count[key] = value

  return doc_count



def ngram_select(doc_count, max_order=MAX_NGRAM_ORDER, tokens_per_order=TOKENS_PER_ORDER):
  """
  DF feature selection for byte-ngram tokenization
  """
  # Work out the set of features to compute IG
  features = set()
  for i in range(1, max_order+1):
    d = dict( (k, doc_count[k]) for k in doc_count if len(k) == i)
    features |= set(sorted(d, key=d.get, reverse=True)[:tokens_per_order])
  features = sorted(features)
  
  return features



if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-f","--features", metavar='FEATURE_FILE', help="output features to FEATURE_FILE")
  parser.add_argument("--tokens_per_order", metavar='N', type=int, help="consider top N tokens per ngram order")
  parser.add_argument("--tokens", metavar='N', type=int, help="consider top N tokens")
  parser.add_argument("--max_order", type=int, help="highest n-gram order to use", default=MAX_NGRAM_ORDER)
  parser.add_argument("--doc_count", nargs='?', const=True, metavar='DOC_COUNT_PATH', help="output full mapping of feature->frequency to DOC_COUNT_PATH")
  parser.add_argument("--bucketlist", help="read list of buckets from")
  parser.add_argument("model", metavar='MODEL_DIR', help="read index and produce output in MODEL_DIR")
  
  args = parser.parse_args()

  if args.tokens and args.tokens_per_order:
    parser.error("--tokens and --tokens_per_order are mutually exclusive")

  # if neither --tokens nor --tokens_per_order is given, default behaviour is tokens_per_order
  if not(args.tokens) and not(args.tokens_per_order):
    args.tokens_per_order = TOKENS_PER_ORDER
  
  if args.features:
    feature_path = args.features
  else:
    feature_path = os.path.join(args.model, 'DFfeats')

  if args.bucketlist:
    bucketlist_path = args.bucketlist 
  else:
    bucketlist_path = os.path.join(args.model, 'bucketlist')

  # display paths
  print "buckets path:", bucketlist_path
  print "features output path:", feature_path
  if args.tokens_per_order:
    print "max ngram order:", args.max_order
    print "tokens per order:", args.tokens_per_order
  else:
    print "tokens:", args.tokens

  with open(bucketlist_path) as f:
    bucketlist = map(str.strip, f)

  doc_count = tally(bucketlist, args.jobs)
  print "unique features:", len(doc_count)
  if args.doc_count:
    # The constant true is used to indicate output to default location
    doc_count_path = os.path.join(args.model, 'DF_all') if args.doc_count == True else args.doc_count
    write_weights(doc_count, doc_count_path)
    print "wrote DF counts for all features to:", doc_count_path

  if args.tokens_per_order:
    # Choose a number of features for each length of token
    feats = ngram_select(doc_count, args.max_order, args.tokens_per_order)
  else:
    # Choose a number of features overall
    feats = sorted( sorted(doc_count, key=doc_count.get, reverse=True)[:args.tokens] )
  print "selected features: ", len(feats)

  write_features(feats, feature_path)
  print 'wrote features to "%s"' % feature_path 

  

########NEW FILE########
__FILENAME__ = IGweight
#!/usr/bin/env python
"""
IGWeight.py - 
Compute IG Weights given a set of tokenized buckets and a feature set

Marco Lui, January 2013

Based on research by Marco Lui and Tim Baldwin.

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

import os, sys, argparse 
import csv
import numpy
import multiprocessing as mp
from itertools import tee, imap, islice
from collections import defaultdict
from contextlib import closing

from common import unmarshal_iter, MapPool, Enumerator, write_weights, read_features 

def entropy(v, axis=0):
  """
  Optimized implementation of entropy. This version is faster than that in 
  scipy.stats.distributions, particularly over long vectors.
  """
  v = numpy.array(v, dtype='float')
  s = numpy.sum(v, axis=axis)
  with numpy.errstate(divide='ignore', invalid='ignore'):
    rhs = numpy.nansum(v * numpy.log(v), axis=axis) / s
    r = numpy.log(s) - rhs
  # Where dealing with binarized events, it is possible that an event always
  # occurs and thus has 0 information. In this case, the negative class
  # will have frequency 0, resulting in log(0) being computed as nan.
  # We replace these nans with 0
  nan_index = numpy.isnan(rhs)
  if nan_index.any():
    r[nan_index] = 0
  return r

def setup_pass_IG(features, dist, binarize, suffix):
  """
  @param features the list of features to compute IG for
  @param dist the background distribution
  @param binarize (boolean) compute IG binarized per-class if True
  @param suffix of files in bucketdir to process
  """
  global __features, __dist, __binarize, __suffix
  __features = features
  __dist = dist
  __binarize = binarize
  __suffix = suffix

def pass_IG(buckets):
  """
  In this pass we compute the information gain for each feature, binarized 
  with respect to each language as well as unified over the set of all 
  classes. 

  @global __features the list of features to compute IG for
  @global __dist the background distribution
  @global __binarize (boolean) compute IG binarized per-class if True
  @global __suffix of files in bucketdir to process
  @param buckets a list of buckets. Each bucket must be a directory that contains files 
                 with the appropriate suffix. Each file must contain marshalled 
                 (term, event_id, count) triplets.
  """
  global __features, __dist, __binarize, __suffix
   
  # We first tally the per-event frequency of each
  # term in our selected feature set.
  term_freq = defaultdict(lambda: defaultdict(int))
  term_index = defaultdict(Enumerator())

  for bucket in buckets:
		for path in os.listdir(bucket):
			if path.endswith(__suffix):
				for key, event_id, count in unmarshal_iter(os.path.join(bucket,path)):
					# Select only our listed features
					if key in __features:
						term_index[key]
						term_freq[key][event_id] += count

  num_term = len(term_index)
  num_event = len(__dist)

  cm_pos = numpy.zeros((num_term, num_event), dtype='int')

  for term,term_id in term_index.iteritems():
    # update event matrix
    freq = term_freq[term]
    for event_id, count in freq.iteritems():
      cm_pos[term_id, event_id] = count
  cm_neg = __dist - cm_pos
  cm = numpy.dstack((cm_neg, cm_pos))

  if not __binarize:
    # non-binarized event space
    x = cm.sum(axis=1)
    term_w = x / x.sum(axis=1)[:, None].astype(float)

    # Entropy of the term-present/term-absent events
    e = entropy(cm, axis=1)

    # Information Gain with respect to the set of events
    ig = entropy(__dist) - (term_w * e).sum(axis=1)

  else:
    # binarized event space
    # Compute IG binarized with respect to each event
    ig = list()
    for event_id in xrange(num_event):
      num_doc = __dist.sum()
      prior = numpy.array((num_doc - __dist[event_id], __dist[event_id]), dtype=float) / num_doc

      cm_bin = numpy.zeros((num_term, 2, 2), dtype=int) # (term, p(term), p(lang|term))
      cm_bin[:,0,:] = cm.sum(axis=1) - cm[:,event_id,:]
      cm_bin[:,1,:] = cm[:,event_id,:]

      e = entropy(cm_bin, axis=1)
      x = cm_bin.sum(axis=1)
      term_w = x / x.sum(axis=1)[:, None].astype(float)

      ig.append( entropy(prior) - (term_w * e).sum(axis=1) )
    ig = numpy.vstack(ig)

  terms = sorted(term_index, key=term_index.get)
  return terms, ig


def compute_IG(bucketlist, features, dist, binarize, suffix, job_count=None):
  pass_IG_args = (features, dist, binarize, suffix)

  num_chunk = len(bucketlist)
  weights = []
  terms = []

  with MapPool(job_count, setup_pass_IG, pass_IG_args) as f:
    pass_IG_out = f(pass_IG, bucketlist)

    for i, (t, w) in enumerate(pass_IG_out):
      weights.append(w)
      terms.extend(t)
      print "processed chunk (%d/%d) [%d terms]" % (i+1, num_chunk, len(t))

  if binarize:
    weights = numpy.hstack(weights).transpose()
  else:
    weights = numpy.concatenate(weights)
  terms = ["".join(t) for t in terms]

  return zip(terms, weights)

def read_dist(path):
  """
  Read the distribution from a file containing item, count pairs.
  @param path path to read form
  """
  with open(path) as f:
    reader = csv.reader(f)
    return numpy.array(zip(*reader)[1], dtype=int)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-f","--features", metavar='FEATURE_FILE', help="read features from FEATURE_FILE")
  parser.add_argument("-w","--weights", metavar='WEIGHTS', help="output weights to WEIGHTS")
  parser.add_argument("-d","--domain", action="store_true", default=False, help="compute IG with respect to domain")
  parser.add_argument("-b","--binarize", action="store_true", default=False, help="binarize the event space in the IG computation")
  parser.add_argument("-l","--lang", action="store_true", default=False, help="compute IG with respect to language")
  parser.add_argument("model", metavar='MODEL_DIR', help="read index and produce output in MODEL_DIR")
  parser.add_argument("buckets", nargs='*', help="read bucketlist from")

  args = parser.parse_args()
  if not(args.domain or args.lang) or (args.domain and args.lang):
    parser.error("exactly one of domain(-d) or language (-l) must be specified")

  if args.features:
    feature_path = args.features
  else:
    feature_path = os.path.join(args.model, 'DFfeats')

  if args.buckets:
    bucketlist_paths = args.buckets
  else:
    bucketlist_paths = [os.path.join(args.model, 'bucketlist')]

  if not os.path.exists(feature_path):
    parser.error('{0} does not exist'.format(feature_path))

  features = read_features(feature_path)

  if args.domain:
    index_path = os.path.join(args.model,'domain_index')
    suffix = '.domain'
  elif args.lang:
    index_path = os.path.join(args.model,'lang_index')
    suffix = '.lang'
  else:
    raise ValueError("no event specified")

  if args.weights:
    weights_path = args.weights
  else:
    weights_path = os.path.join(args.model, 'IGweights' + suffix + ('.bin' if args.binarize else ''))

  # display paths
  print "model path:", args.model 
  print "buckets path:", bucketlist_paths
  print "features path:", feature_path
  print "weights path:", weights_path
  print "index path:", index_path
  print "suffix:", suffix

  print "computing information gain"
  # Compile buckets together
  bucketlist = zip(*(map(str.strip, open(p)) for p in bucketlist_paths))

  # Check that each bucketlist has the same number of buckets
  assert len(set(map(len,bucketlist))) == 1, "incompatible bucketlists!"

  dist = read_dist(index_path)
  ig = compute_IG(bucketlist, features, dist, args.binarize, suffix, args.jobs)

  write_weights(ig, weights_path)

########NEW FILE########
__FILENAME__ = index
#!/usr/bin/env python
"""
index.py - 
Index a corpus that is stored in a directory hierarchy as follows:

- corpus
  - domain1
    - language1
      - file1
      - file2
      - ...
    - language2
    - ...
  - domain2
    - language1
      - file1
      - file2
      - ...
    - language2
    - ...
  - ...

This produces 3 files: 
* index: a list of paths, together with the langid and domainid as integers
* lang_index: a list of languages in ascending order of id, with the count for each
* domain_index: a list of domains in ascending order of id, with the count for each

Marco Lui, January 2013

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

######
# Default values
# Can be overriden with command-line options
######
TRAIN_PROP = 1.0 # probability than any given document is selected
MIN_DOMAIN = 1 # minimum number of domains a language must be present in to be included

import os, sys, argparse
import csv
import random
import numpy
from itertools import tee, imap, islice
from collections import defaultdict

from common import Enumerator, makedir

class CorpusIndexer(object):
  """
  Class to index the contents of a corpus
  """
  def __init__(self, root, min_domain=MIN_DOMAIN, proportion=TRAIN_PROP, langs=None, domains=None, line_level=False):
    self.root = root
    self.min_domain = min_domain
    self.proportion = proportion 

    if langs is None:
      self.lang_index = defaultdict(Enumerator())
    else:
      # pre-specified lang set
      self.lang_index = dict((k,v) for v,k in enumerate(langs))

    if domains is None:
      self.domain_index = defaultdict(Enumerator())
    else:
      # pre-specified domain set
      self.domain_index = dict((k,v) for v,k in enumerate(domains))

    self.coverage_index = defaultdict(set)
    self.items = list()

    if os.path.isdir(root):
      # root supplied was the root of a directory structure
      candidates = []
      for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        for docname in filenames:
          candidates.append(os.path.join(dirpath, docname))
    else:
      # root supplied was a file, interpet as list of paths
      candidates = map(str.strip, open(root))

    if line_level:
      self.index_line(candidates)
    else:
      self.index(candidates)

    self.prune_min_domain(self.min_domain)

  def index_line(self, candidates):
    """
    Line-level indexing. Assumes the list of candidates is file-per-class,
    where each line is a document.
    """
    if self.proportion < 1.0:
      raise NotImplementedError("proportion selection not available for file-per-class")

    for path in candidates:
      d, lang = os.path.split(path)
      d, domain = os.path.split(d)

      # index the language and the domain
      try:
        # TODO: If lang is pre-specified but not domain, we can end up 
        #       enumerating empty domains.
        domain_id = self.domain_index[domain]
        lang_id = self.lang_index[lang]
      except KeyError:
        # lang or domain outside a pre-specified set so
        # skip this document.
        continue

      # add the domain-lang relation to the coverage index
      self.coverage_index[domain].add(lang)

      with open(path) as f:
        for i,row in enumerate(f):
          docname = "line{0}".format(i)
          self.items.append((domain_id,lang_id,docname,path))

  def index(self, candidates):

    # build a list of paths
    for path in candidates:
      # Each file has 'proportion' chance of being selected.
      if random.random() < self.proportion:

        # split the path into identifying components
        d, docname = os.path.split(path)
        d, lang = os.path.split(d)
        d, domain = os.path.split(d)

        # index the language and the domain
        try:
          # TODO: If lang is pre-specified but not domain, we can end up 
          #       enumerating empty domains.
          domain_id = self.domain_index[domain]
          lang_id = self.lang_index[lang]
        except KeyError:
          # lang or domain outside a pre-specified set so
          # skip this document.
          continue

        # add the domain-lang relation to the coverage index
        self.coverage_index[domain].add(lang)

        # add the item to our list
        self.items.append((domain_id,lang_id,docname,path))

  def prune_min_domain(self, min_domain):
    # prune files for all languages that do not occur in at least min_domain 
     
    # Work out which languages to reject as they are not present in at least 
    # the required number of domains
    lang_domain_count = defaultdict(int)
    for langs in self.coverage_index.values():
      for lang in langs:
        lang_domain_count[lang] += 1
    reject_langs = set( l for l in lang_domain_count if lang_domain_count[l] < min_domain)

    # Remove the languages from the indexer
    if reject_langs:
      #print "reject (<{0} domains): {1}".format(min_domain, sorted(reject_langs))
      reject_ids = set(self.lang_index[l] for l in reject_langs)
    
      new_lang_index = defaultdict(Enumerator())
      lm = dict()
      for k,v in self.lang_index.items():
        if v not in reject_ids:
          new_id = new_lang_index[k]
          lm[v] = new_id

      # Eliminate all entries for the languages
      self.items = [ (d, lm[l], n, p) for (d, l, n, p) in self.items if l in lm]

      self.lang_index = new_lang_index


  @property
  def dist_lang(self):
    """
    @returns A vector over frequency counts for each language
    """
    retval = numpy.zeros((len(self.lang_index),), dtype='int')
    for d, l, n, p in self.items:
      retval[l] += 1
    return retval

  @property
  def dist_domain(self):
    """
    @returns A vector over frequency counts for each domain 
    """
    retval = numpy.zeros((len(self.domain_index),), dtype='int')
    for d, l, n, p in self.items:
      retval[d] += 1
    return retval

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--line", action="store_true",
      help="treat each line in a file as a document")
  parser.add_argument("-p","--proportion", type=float, default=TRAIN_PROP,
      help="proportion of training data to use" )
  parser.add_argument("-m","--model", help="save output to MODEL_DIR", metavar="MODEL_DIR")
  parser.add_argument("-d","--domain", metavar="DOMAIN", action='append',
      help="use DOMAIN - can be specified multiple times (uses all domains found if not specified)")
  parser.add_argument("-l","--lang", metavar="LANG", action='append',
      help="use LANG - can be specified multiple times (uses all langs found if not specified)")
  parser.add_argument("--min_domain", type=int, default=MIN_DOMAIN,
      help="minimum number of domains a language must be present in" )
  parser.add_argument("corpus", help="read corpus from CORPUS_DIR", metavar="CORPUS_DIR")

  args = parser.parse_args()

  corpus_name = os.path.basename(args.corpus)
  if args.model:
    model_dir = args.model
  else:
    model_dir = os.path.join('.', corpus_name+'.model')

  makedir(model_dir)

  langs_path = os.path.join(model_dir, 'lang_index')
  domains_path = os.path.join(model_dir, 'domain_index')
  index_path = os.path.join(model_dir, 'paths')

  # display paths
  print "corpus path:", args.corpus
  print "model path:", model_dir
  print "writing langs to:", langs_path
  print "writing domains to:", domains_path
  print "writing index to:", index_path

  if args.line:
    print "indexing documents at the line level"

  indexer = CorpusIndexer(args.corpus, min_domain=args.min_domain, proportion=args.proportion,
                          langs = args.lang, domains = args.domain, line_level=args.line)

  # Compute mappings between files, languages and domains
  lang_dist = indexer.dist_lang
  lang_index = indexer.lang_index
  lang_info = ' '.join(("{0}({1})".format(k, lang_dist[v]) for k,v in lang_index.items()))
  print "langs({0}): {1}".format(len(lang_dist), lang_info)

  domain_dist = indexer.dist_domain
  domain_index = indexer.domain_index
  domain_info = ' '.join(("{0}({1})".format(k, domain_dist[v]) for k,v in domain_index.items()))
  print "domains({0}): {1}".format(len(domain_dist), domain_info)

  print "identified {0} documents".format(len(indexer.items))

  # output the language index
  with open(langs_path,'w') as f:
    writer = csv.writer(f)
    writer.writerows((l, lang_dist[lang_index[l]]) 
        for l in sorted(lang_index.keys(), key=lang_index.get))

  # output the domain index
  with open(domains_path,'w') as f:
    writer = csv.writer(f)
    writer.writerows((d, domain_dist[domain_index[d]]) 
        for d in sorted(domain_index.keys(), key=domain_index.get))

  # output items found
  with open(index_path,'w') as f:
    writer = csv.writer(f)
    writer.writerows( sorted(set((d,l,p) for (d,l,n,p) in indexer.items)) )

########NEW FILE########
__FILENAME__ = LDfeatureselect
#!/usr/bin/env python
"""
LDfeatureselect.py - 
LD (Lang-Domain) feature extractor
Marco Lui November 2011

Based on research by Marco Lui and Tim Baldwin.

Copyright 2011 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

######
# Default values
# Can be overriden with command-line options
######
FEATURES_PER_LANG = 300 # number of features to select for each language

import os, sys, argparse
import csv
import marshal
import numpy
import multiprocessing as mp
from collections import defaultdict

from common import read_weights, Enumerator, write_features

def select_LD_features(ig_lang, ig_domain, feats_per_lang, ignore_domain=False):
  """
  @param ignore_domain boolean to indicate whether to use domain weights
  """
  assert (ig_domain is None) or (len(ig_lang) == len(ig_domain))
  num_lang = len(ig_lang.values()[0])
  num_term = len(ig_lang)

  term_index = defaultdict(Enumerator())


  ld = numpy.empty((num_lang, num_term), dtype=float)

  for term in ig_lang:
    term_id = term_index[term]
    if ignore_domain:
      ld[:, term_id] = ig_lang[term]
    else:
      ld[:, term_id] = ig_lang[term] - ig_domain[term]

  terms = sorted(term_index, key=term_index.get)
  # compile the final feature set
  selected_features = dict()
  for lang_id, lang_w in enumerate(ld):
    term_inds = numpy.argsort(lang_w)[-feats_per_lang:]
    selected_features[lang_id] = [terms[t] for t in term_inds]

  return selected_features
    
if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-o","--output", metavar="OUTPUT_PATH", help = "write selected features to OUTPUT_PATH")
  parser.add_argument("--feats_per_lang", type=int, metavar='N', help="select top N features for each language", default=FEATURES_PER_LANG)
  parser.add_argument("--per_lang", action="store_true", default=False, help="produce a list of features selecter per-language")
  parser.add_argument("--no_domain_ig", action="store_true", default=False, help="use only per-langugage IG in LD calculation")
  parser.add_argument("model", metavar='MODEL_DIR', help="read index and produce output in MODEL_DIR")
  args = parser.parse_args()

  lang_w_path = os.path.join(args.model, 'IGweights.lang.bin')
  domain_w_path = os.path.join(args.model, 'IGweights.domain')
  feature_path = args.output if args.output else os.path.join(args.model, 'LDfeats')

  # display paths
  print "model path:", args.model
  print "lang weights path:", lang_w_path
  print "domain weights path:", domain_w_path
  print "feature output path:", feature_path

  lang_w = read_weights(lang_w_path)
  domain_w = read_weights(domain_w_path) if not args.no_domain_ig else None

  features_per_lang = select_LD_features(lang_w, domain_w, args.feats_per_lang, ignore_domain=args.no_domain_ig)
  if args.per_lang:
    with open(feature_path + '.perlang', 'w') as f:
      writer = csv.writer(f)
      for i in range(len(features_per_lang)):
        writer.writerow(map(repr,features_per_lang[i]))
      

  final_feature_set = reduce(set.union, map(set, features_per_lang.values()))
  print 'selected %d features' % len(final_feature_set)

  write_features(sorted(final_feature_set), feature_path)
  print 'wrote features to "%s"' % feature_path 


########NEW FILE########
__FILENAME__ = NBtrain
#!/usr/bin/env python
"""
NBtrain.py - 
Model generator for langid.py

Marco Lui, January 2013

Based on research by Marco Lui and Tim Baldwin.

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""
MAX_CHUNK_SIZE = 100 # maximum number of files to tokenize at once
NUM_BUCKETS = 64 # number of buckets to use in k-v pair generation

import base64, bz2, cPickle
import os, sys, argparse, csv
import array
import numpy as np
import tempfile
import marshal
import atexit, shutil
import multiprocessing as mp
import gzip
from collections import deque, defaultdict
from contextlib import closing

from common import chunk, unmarshal_iter, read_features, index, MapPool

def state_trace(text):
  """
  Returns counts of how often each state was entered
  """
  global __nm_arr
  c = defaultdict(int)
  state = 0
  for letter in map(ord,text):
    state = __nm_arr[(state << 8) + letter]
    c[state] += 1
  return c

def setup_pass_tokenize(nm_arr, output_states, tk_output, b_dirs, line_level):
  """
  Set the global next-move array used by the aho-corasick scanner
  """
  global __nm_arr, __output_states, __tk_output, __b_dirs, __line_level
  __nm_arr = nm_arr
  __output_states = output_states
  __tk_output = tk_output
  __b_dirs = b_dirs
  __line_level = line_level

def pass_tokenize(arg):
  """
  Tokenize documents and do counts for each feature
  Split this into buckets chunked over features rather than documents

  chunk_paths contains label, path pairs because we only know the
  labels per-path, but in line mode there will be multiple documents
  per path and we don't know how many those are.
  """
  global __output_states, __tk_output, __b_dirs, __line_level
  chunk_id, chunk_paths = arg
  term_freq = defaultdict(int)

  # Tokenize each document and add to a count of (doc_id, f_id) frequencies
  doc_count = 0
  labels = []
  for label, path in chunk_paths:
    with open(path) as f:
      if __line_level:
        # each line is treated as a document
        for text in f:
          count = state_trace(text)
          for state in (set(count) & __output_states):
            for f_id in __tk_output[state]:
              term_freq[doc_count, f_id] += count[state]
          doc_count += 1
          labels.append(label)

      else:
        text = f.read()
        count = state_trace(text)
        for state in (set(count) & __output_states):
          for f_id in __tk_output[state]:
            term_freq[doc_count, f_id] += count[state]
        doc_count += 1
        labels.append(label)

  # Distribute the aggregated counts into buckets
  __procname = mp.current_process().name
  __buckets = [gzip.open(os.path.join(p,__procname+'.index'), 'a') for p in __b_dirs]
  bucket_count = len(__buckets)
  for doc_id, f_id in term_freq:
    bucket_index = hash(f_id) % bucket_count
    count = term_freq[doc_id, f_id]
    item = ( f_id, chunk_id, doc_id, count )
    __buckets[bucket_index].write(marshal.dumps(item))

  for f in __buckets:
    f.close()

  return chunk_id, doc_count, len(term_freq), labels

def setup_pass_ptc(cm, num_instances, chunk_offsets):
  global __cm, __num_instances, __chunk_offsets
  __cm = cm
  __num_instances = num_instances
  __chunk_offsets = chunk_offsets

def pass_ptc(b_dir):
  """
  Take a bucket, form a feature map, compute the count of
  each feature in each class.
  @param b_dir path to the bucket directory
  @returns (read_count, f_ids, prod) 
  """
  global __cm, __num_instances, __chunk_offsets

  terms = defaultdict(lambda : np.zeros((__num_instances,), dtype='int'))

  read_count = 0
  for path in os.listdir(b_dir):
    if path.endswith('.index'):
      for f_id, chunk_id, doc_id, count in unmarshal_iter(os.path.join(b_dir, path)):
        index = doc_id + __chunk_offsets[chunk_id]
        terms[f_id][index] = count
        read_count += 1

  f_ids, f_vs = zip(*terms.items())
  fm = np.vstack(f_vs)
  # The calculation of the term-class distribution is done per-chunk rather
  # than globally for memory efficiency reasons.
  prod = np.dot(fm, __cm)

  return read_count, f_ids, prod

def learn_nb_params(items, num_langs, tk_nextmove, tk_output, temp_path, args):
  """
  @param items label, path pairs
  """
  global outdir

  print "learning NB parameters on {} items".format(len(items))

  # Generate the feature map
  nm_arr = mp.Array('i', tk_nextmove, lock=False)

  if args.jobs:
    tasks = args.jobs * 2
  else:
    tasks = mp.cpu_count() * 2

  # Ensure chunksize of at least 1, but not exceeding specified chunksize
  chunksize = max(1, min(len(items) / tasks, args.chunksize))

  outdir = tempfile.mkdtemp(prefix="NBtrain-",suffix='-buckets', dir=temp_path)
  b_dirs = [ os.path.join(outdir,"bucket{0}".format(i)) for i in range(args.buckets) ]

  for d in b_dirs:
    os.mkdir(d)

  output_states = set(tk_output)
  
  # Divide all the items to be processed into chunks, and enumerate each chunk.
  item_chunks = list(chunk(items, chunksize))
  num_chunks = len(item_chunks)
  print "about to tokenize {} chunks".format(num_chunks)
  
  pass_tokenize_arg = enumerate(item_chunks)
  pass_tokenize_params = (nm_arr, output_states, tk_output, b_dirs, args.line) 
  with MapPool(args.jobs, setup_pass_tokenize, pass_tokenize_params) as f:
    pass_tokenize_out = f(pass_tokenize, pass_tokenize_arg)
  
    write_count = 0
    chunk_sizes = {}
    chunk_labels = []
    for i, (chunk_id, doc_count, writes, labels) in enumerate(pass_tokenize_out):
      write_count += writes
      chunk_sizes[chunk_id] = doc_count
      chunk_labels.append((chunk_id, labels))
      print "processed chunk ID:{0} ({1}/{2}) [{3} keys]".format(chunk_id, i+1, num_chunks, writes)

  print "wrote a total of %d keys" % write_count

  num_instances = sum(chunk_sizes.values())
  print "processed a total of %d instances" % num_instances

  chunk_offsets = {}
  for i in range(len(chunk_sizes)):
    chunk_offsets[i] = sum(chunk_sizes[x] for x in range(i))

  # Build CM based on re-ordeing chunk
  cm = np.zeros((num_instances, num_langs), dtype='bool')
  for chunk_id, chunk_label in chunk_labels:
    for doc_id, lang_id in enumerate(chunk_label):
      index = doc_id + chunk_offsets[chunk_id]
      cm[index, lang_id] = True

  pass_ptc_params = (cm, num_instances, chunk_offsets)
  with MapPool(args.jobs, setup_pass_ptc, pass_ptc_params) as f:
    pass_ptc_out = f(pass_ptc, b_dirs)

    def pass_ptc_progress():
      for i,v in enumerate(pass_ptc_out):
        yield v
        print "processed chunk ({0}/{1})".format(i+1, len(b_dirs))

    reads, ids, prods = zip(*pass_ptc_progress())
    read_count = sum(reads)
    print "read a total of %d keys (%d short)" % (read_count, write_count - read_count)

  num_features = max( i for v in tk_output.values() for i in v) + 1
  prod = np.zeros((num_features, cm.shape[1]), dtype=int)
  prod[np.concatenate(ids)] = np.vstack(prods)

  # This is where the smoothing occurs
  ptc = np.log(1 + prod) - np.log(num_features + prod.sum(0))

  nb_ptc = array.array('d')
  for term_dist in ptc.tolist():
    nb_ptc.extend(term_dist)

  pc = np.log(cm.sum(0))
  nb_pc = array.array('d', pc)

  return nb_pc, nb_ptc

@atexit.register
def cleanup():
  global outdir 
  try:
    shutil.rmtree(outdir)
  except NameError:
    pass

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-t", "--temp", metavar='TEMP_DIR', help="store buckets in TEMP_DIR instead of in MODEL_DIR/buckets")
  parser.add_argument("-s", "--scanner", metavar='SCANNER', help="use SCANNER for feature counting")
  parser.add_argument("-o", "--output", metavar='OUTPUT', help="output langid.py-compatible model to OUTPUT")
  #parser.add_argument("-i","--index",metavar='INDEX',help="read list of training document paths from INDEX")
  parser.add_argument("model", metavar='MODEL_DIR', help="read index and produce output in MODEL_DIR")
  parser.add_argument("--chunksize", type=int, help='maximum chunk size (number of files)', default=MAX_CHUNK_SIZE)
  parser.add_argument("--buckets", type=int, metavar='N', help="distribute features into N buckets", default=NUM_BUCKETS)
  parser.add_argument("--line", action="store_true", help="treat each line in a file as a document")
  args = parser.parse_args()

  if args.temp:
    temp_path = args.temp
  else:
    temp_path = os.path.join(args.model, 'buckets')

  if args.scanner:
    scanner_path = args.scanner
  else:
    scanner_path = os.path.join(args.model, 'LDfeats.scanner')

  if args.output:
    output_path = args.output
  else:
    output_path = os.path.join(args.model, 'model')

  index_path = os.path.join(args.model, 'paths')
  lang_path = os.path.join(args.model, 'lang_index')

  # display paths
  print "model path:", args.model
  print "temp path:", temp_path
  print "scanner path:", scanner_path
  print "output path:", output_path

  if args.line:
    print "treating each LINE as a document"

  # read list of training files
  with open(index_path) as f:
    reader = csv.reader(f)
    items = [ (int(l),p) for _,l,p in reader ]

  # read scanner
  with open(scanner_path) as f:
    tk_nextmove, tk_output, _ = cPickle.load(f)

  # read list of languages in order
  with open(lang_path) as f:
    reader = csv.reader(f)
    langs = zip(*reader)[0]
    
  nb_classes = langs
  nb_pc, nb_ptc = learn_nb_params(items, len(langs), tk_nextmove, tk_output, temp_path, args)

  # output the model
  model = nb_ptc, nb_pc, nb_classes, tk_nextmove, tk_output
  string = base64.b64encode(bz2.compress(cPickle.dumps(model)))
  with open(output_path, 'w') as f:
    f.write(string)
  print "wrote model to %s (%d bytes)" % (output_path, len(string))

########NEW FILE########
__FILENAME__ = scanner
#!/usr/bin/env python
"""
scanner.py - 
Assemble a "feature scanner" using Aho-Corasick string matching.
This takes a list of features (byte sequences) and builds a DFA 
that when run on a byte stream can identify how often each of 
the features is present in a single pass over the stream.

Marco Lui, January 2013

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

import cPickle
import os, sys, argparse 
import array
from collections import deque, defaultdict
from common import read_features

class Scanner(object):
  alphabet = map(chr, range(1<<8))
  """
  Implementation of Aho-Corasick string matching.
  This class should be instantiated with a set of keywords, which
  will then be the only tokens generated by the class's search method,
  """
  @classmethod
  def from_file(cls, path):
    with open(path) as f:
      tk_nextmove, tk_output, feats = cPickle.load(f)
    if isinstance(feats, dict):
      # The old scanner format had two identical dictionaries as the last
      # two items in the tuple. This format can still be used by langid.py,
      # but it does not carry the feature list, and so cannot be unpacked
      # back into a Scanner object.
      raise ValueError("old format scanner - please retrain. see code for details.")
    # tk_output is a mapping from state to a list of feature indices.
    # because of the way the scanner class is written, it needs a mapping
    # from state to the feature itself. We rebuild this here.
    tk_output_f = dict( (k,[feats[i] for i in v]) for k,v in tk_output.iteritems() )
    scanner = cls.__new__(cls)
    scanner.__setstate__((tk_nextmove, tk_output_f))
    return scanner
    
  def __init__(self, keywords):
    self.build(keywords)

  def __call__(self, value):
    return self.search(value)

  def build(self, keywords):
    goto = dict()
    fail = dict()
    output = defaultdict(set)

    # Algorithm 2
    newstate = 0
    for a in keywords:
      state = 0
      j = 0
      while (j < len(a)) and (state, a[j]) in goto:
        state = goto[(state, a[j])]
        j += 1
      for p in range(j, len(a)):
        newstate += 1
        goto[(state, a[p])] = newstate
        #print "(%d, %s) -> %d" % (state, a[p], newstate)
        state = newstate
      output[state].add(a)
    for a in self.alphabet:
      if (0,a) not in goto: 
        goto[(0,a)] = 0

    # Algorithm 3
    queue = deque()
    for a in self.alphabet:
      if goto[(0,a)] != 0:
        s = goto[(0,a)]
        queue.append(s)
        fail[s] = 0
    while queue:
      r = queue.popleft()
      for a in self.alphabet:
        if (r,a) in goto:
          s = goto[(r,a)]
          queue.append(s)
          state = fail[r]
          while (state,a) not in goto:
            state = fail[state]
          fail[s] = goto[(state,a)]
          #print "f(%d) -> %d" % (s, goto[(state,a)]), output[fail[s]]
          if output[fail[s]]:
            output[s].update(output[fail[s]])

    # Algorithm 4
    self.nextmove = {}
    for a in self.alphabet:
      self.nextmove[(0,a)] = goto[(0,a)]
      if goto[(0,a)] != 0:
        queue.append(goto[(0,a)])
    while queue:
      r = queue.popleft()
      for a in self.alphabet:
        if (r,a) in goto:
          s = goto[(r,a)]
          queue.append(s)
          self.nextmove[(r,a)] = s
        else:
          self.nextmove[(r,a)] = self.nextmove[(fail[r],a)]

    # convert the output to tuples, as tuple iteration is faster
    # than set iteration
    self.output = dict((k, tuple(output[k])) for k in output)

    # Next move encoded as a single array. The index of the next state
    # is located at current state * alphabet size  + ord(c).
    # The choice of 'H' array typecode limits us to 64k states.
    def generate_nm_arr(typecode):
      def nextstate_iter():
        # State count starts at 0, so the number of states is the number of i
        # the last state (newstate) + 1
        for state in xrange(newstate+1):
          for letter in self.alphabet:
            yield self.nextmove[(state, letter)]
      return array.array(typecode, nextstate_iter())
    try:
      self.nm_arr = generate_nm_arr('H')
    except OverflowError:
      # Could not fit in an unsigned short array, let's try an unsigned long array.
      self.nm_arr = generate_nm_arr('L')

  def __getstate__(self):
    """
    Compiled nextmove and output.
    """
    return (self.nm_arr, self.output)

  def __setstate__(self, value):
    nm_array, output = value
    self.nm_arr = nm_array
    self.output = output
    self.nextmove = {}
    for i, next_state in enumerate(nm_array):
      state = i / 256
      letter = chr(i % 256)
      self.nextmove[(state, letter)] = next_state 

  def search(self, string):
    state = 0
    for letter in map(ord,string):
      state = self.nm_arr[(state << 8) + letter]
      for key in self.output.get(state, []):
        yield key

def build_scanner(features):
  """
  In difference to the Scanner class, this function unwraps a layer of indirection in
  the detection of features. It translates the string output of the scanner's output
  mapping into the index values (positions in the list) of the features in the supplied
  feature set. This is very useful where we are only interested in the relative frequencies
  of features.

  @param features a list of features (byte sequences)
  @returns a compiled scanner model
  """
  feat_index = index(features)

  # Build the actual scanner
  print "building scanner"
  scanner = Scanner(features)
  tk_nextmove, raw_output = scanner.__getstate__()

  # tk_output is the output function of the scanner. It should generate indices into
  # the feature space directly, as this saves a lookup
  tk_output = {}
  for k,v in raw_output.items():
    tk_output[k] = tuple(feat_index[f] for f in v)
  return tk_nextmove, tk_output


def index(seq):
  """
  Build an index for a sequence of items. Assumes
  that the items in the sequence are unique.
  @param seq the sequence to index
  @returns a dictionary from item to position in the sequence
  """
  return dict((k,v) for (v,k) in enumerate(seq))

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("input", metavar="INPUT", help="build a scanner for INPUT. If input is a directory, read INPUT/LDfeats")
  parser.add_argument("-o","--output", help="output scanner to OUTFILE", metavar="OUTFILE")
  args = parser.parse_args()

  if os.path.isdir(args.input):
    input_path = os.path.join(args.input, 'LDfeats')
  else:
    input_path = args.input

  if args.output:
    output_path = args.output
  else:
    output_path = input_path + '.scanner'

  # display paths
  print "input path:", input_path
  print "output path:", output_path

  nb_features = read_features(input_path)
  tk_nextmove, tk_output = build_scanner(nb_features)
  scanner = tk_nextmove, tk_output, nb_features

  with open(output_path, 'w') as f:
    cPickle.dump(scanner, f)
  print "wrote scanner to {0}".format(output_path)

########NEW FILE########
__FILENAME__ = tokenize
#!/usr/bin/env python
"""
tokenize.py - 
Tokenizer for langid.py training system. This takes a list of files and tokenizes them
in parallel.

Marco Lui, January 2013

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

######
# Default values
# Can be overriden with command-line options
######
MIN_NGRAM_ORDER = 1 # smallest order of n-grams to consider
MAX_NGRAM_ORDER = 4 # largest order of n-grams to consider
TOP_DOC_FREQ = 15000 # number of tokens to consider for each order
NUM_BUCKETS = 64 # number of buckets to use in k-v pair generation
CHUNKSIZE = 50 # maximum size of chunk (number of files tokenized - less = less memory use)

import os, sys, argparse
import csv
import shutil
import marshal
import multiprocessing as mp
import random
import atexit
import gzip
import tempfile

from itertools import tee 
from collections import defaultdict, Counter

from common import makedir, chunk, MapPool

class NGramTokenizer(object):
  def __init__(self, min_order=1, max_order=3):
    self.min_order = min_order
    self.max_order = max_order

  def __call__(self, seq):
    min_order = self.min_order
    max_order = self.max_order
    t = tee(seq, max_order)
    for i in xrange(max_order):
      for j in xrange(i):
        # advance iterators, ignoring result
        t[i].next()
    while True:
      token = ''.join(tn.next() for tn in t)
      if len(token) < max_order: break
      for n in xrange(min_order-1, max_order):
        yield token[:n+1]
    for a in xrange(max_order-1):
      for b in xrange(min_order, max_order-a):
        yield token[a:a+b]

@atexit.register
def cleanup():
  global b_dirs, complete
  try:
    if not complete:
      for d in b_dirs:
        shutil.rmtree(d)
  except NameError:
    # Failed before globals defined, nothing to clean
    pass

def setup_pass_tokenize(tokenizer, b_dirs, sample_count, sample_size, term_freq, line_level):
  global __tokenizer, __b_dirs, __sample_count, __sample_size, __term_freq, __line_level
  __tokenizer = tokenizer
  __b_dirs = b_dirs
  __sample_count = sample_count
  __sample_size = sample_size
  __term_freq = term_freq
  __line_level = line_level

def pass_tokenize(chunk_items):
  """
  Computes the conditional frequencies of terms. The frequency can be
  either term frequency or document frequency, controlled by a global
  variable. Files are converted into a sequence of terms, which
  are then reduced to either TF or DF. The counts are redistributed to
  buckets via Python's built-in hash function. This is basically an
  inversion setp, so that the counts are now grouped by term rather
  than by document.
  """
  global __maxorder, __b_dirs, __extractor, __sample_count, __sample_size, __term_freq, __line_level
  
  extractor = __tokenizer
  term_lng_freq = defaultdict(lambda: defaultdict(int))
  term_dom_freq = defaultdict(lambda: defaultdict(int))

  for domain_id, lang_id, path in chunk_items:
    with open(path) as f:
      if __sample_count:
        # sampling tokenization
        text = f.read()
        poss = max(1,len(text) - __sample_size) # possibe start locations
        count = min(poss, __sample_count) # reduce number of samples if document is too short
        offsets = random.sample(xrange(poss), count)
        for offset in offsets:
          tokens = extractor(text[offset: offset+__sample_size])
          if args.__term_freq:
            # Term Frequency
            tokenset = Counter(tokens)
          else:
            # Document Frequency
            tokenset = Counter(set(tokens))
          for token, count in tokenset.iteritems():
            term_lng_freq[token][lang_id] += count
            term_dom_freq[token][domain_id] += count
      elif __line_level:
        # line-model - each line in a file should be interpreted as a document
        for line in f:
          tokens = extractor(line)
          if __term_freq:
            # Term Frequency
            tokenset = Counter(tokens)
          else:
            # Document Frequency
            tokenset = Counter(set(tokens))
          for token, count in tokenset.iteritems():
            term_lng_freq[token][lang_id] += count
            term_dom_freq[token][domain_id] += count
          
      else:
        # whole-document tokenization
        tokens = extractor(f.read())
        if __term_freq:
          # Term Frequency
          tokenset = Counter(tokens)
        else:
          # Document Frequency
          tokenset = Counter(set(tokens))
        for token, count in tokenset.iteritems():
          term_lng_freq[token][lang_id] += count
          term_dom_freq[token][domain_id] += count

  # Output the counts to the relevant bucket files. 
  __procname = mp.current_process().name
  b_freq_lang = [gzip.open(os.path.join(p,__procname+'.lang'),'a') for p in __b_dirs]
  b_freq_domain = [gzip.open(os.path.join(p,__procname+'.domain'),'a') for p in __b_dirs]

  for term in term_lng_freq:
    bucket_index = hash(term) % len(b_freq_lang)
    for lang, count in term_lng_freq[term].iteritems():
      b_freq_lang[bucket_index].write(marshal.dumps((term, lang, count)))
    for domain, count in term_dom_freq[term].iteritems():
      b_freq_domain[bucket_index].write(marshal.dumps((term, domain, count)))

  # Close all the open files
  for f in b_freq_lang + b_freq_domain:
    f.close()

  return len(term_lng_freq)

def build_index(items, tokenizer, outdir, buckets=NUM_BUCKETS, 
        jobs=None, chunksize=CHUNKSIZE, sample_count=None, 
        sample_size=None, term_freq=False, line_level=False):
  """
  @param items a list of (domain, language, path) tuples
  """
  global b_dirs, complete

  # Our exitfunc uses this to know whether to delete the tokenized files
  complete = False 

  if jobs is None:
    jobs = mp.cpu_count() + 4

  b_dirs = [ os.path.join(outdir,"bucket{0}".format(i)) for i in range(buckets) ]

  for d in b_dirs:
    os.mkdir(d)

  # PASS 1: Tokenize documents into sets of terms
   
  # If there are few items, make the chunk size such that each job
  # will have 2 chunks
  chunk_size = max(1,min(len(items) / (jobs * 2), chunksize))
  item_chunks = list(chunk(items, chunk_size))
  pass_tokenize_globals = (tokenizer, b_dirs, sample_count, sample_size, term_freq, line_level)

  with MapPool(jobs, setup_pass_tokenize, pass_tokenize_globals) as f:
    pass_tokenize_out = f(pass_tokenize, item_chunks)


    doc_count = defaultdict(int)
    chunk_count = len(item_chunks)
    print "chunk size: {0} ({1} chunks)".format(chunk_size, chunk_count)
    print "job count: {0}".format(jobs)

    if sample_count:
      print "sampling-based tokenization: size {0} count {1}".format(sample_size, sample_count)
    else:
      print "whole-document tokenization"

    for i, keycount in enumerate(pass_tokenize_out):
      print "tokenized chunk (%d/%d) [%d keys]" % (i+1,chunk_count, keycount)

  complete = True

  return b_dirs

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-s", "--scanner", metavar='SCANNER', help="use SCANNER for tokenizing")
  parser.add_argument("--buckets", type=int, metavar='N', help="distribute features into N buckets", default=NUM_BUCKETS)
  parser.add_argument("--min_order", type=int, help="lowest n-gram order to use")
  parser.add_argument("--max_order", type=int, help="highest n-gram order to use")
  parser.add_argument("--word", action='store_true', default=False, help="use 'word' tokenization (currently str.split)")
  parser.add_argument("--chunksize", type=int, help="max chunk size (number of files to tokenize at a time - smaller should reduce memory use)", default=CHUNKSIZE)
  parser.add_argument("--term_freq", action='store_true', help="count term frequency (default is document frequency)")
  parser.add_argument("-t", "--temp", metavar='TEMP_DIR', help="store buckets in TEMP_DIR instead of in MODEL_DIR/buckets")
  parser.add_argument("-o", "--output", help="write list of output buckets to OUTPUT")
  parser.add_argument("--line", action="store_true", help="treat each line in a file as a document")
  parser.add_argument("model", metavar='MODEL_DIR', help="read index and produce output in MODEL_DIR")

  group = parser.add_argument_group('sampling')
  group.add_argument("--sample_size", type=int, help="size of sample for sampling-based tokenization", default=140)
  group.add_argument("--sample_count", type=int, help="number of samples for sampling-based tokenization", default=None)
  
  args = parser.parse_args()

  if args.sample_count and args.line:
    parser.error("sampling in line mode is not implemented")
  

  if args.temp:
    tmp_dir = args.temp
  else:
    tmp_dir = os.path.join(args.model, 'buckets')
  makedir(tmp_dir)

  # We generate a new directory at each invocation, otherwise we run the 
  # risk of conflicting with a previous run without warning.
  buckets_dir = tempfile.mkdtemp(suffix='tokenize',dir=tmp_dir)

  bucketlist_path = args.output if args.output else os.path.join(args.model, 'bucketlist')
  index_path = os.path.join(args.model, 'paths')

  # display paths
  print "index path:", index_path
  print "bucketlist path:", bucketlist_path
  print "buckets path:", buckets_dir

  if args.line:
  	print "treating each LINE as a document"

  with open(index_path) as f:
    reader = csv.reader(f)
    items = list(reader)

  if sum(map(bool,(args.scanner, args.max_order, args.word))) > 1:
    parser.error('can only specify one of --word, --scanner and --max_order')

  # Tokenize
  print "will tokenize %d files" % len(items)
  if args.scanner:
    from scanner import Scanner
    tokenizer = Scanner.from_file(args.scanner)
    print "using provided scanner: ", args.scanner
  elif args.word:
    tokenizer = str.split
    print "using str.split to tokenize"
  else:
    min_order = args.min_order if args.min_order else MIN_NGRAM_ORDER
    max_order = args.max_order if args.max_order else MAX_NGRAM_ORDER
    tokenizer = NGramTokenizer(min_order,max_order)
    print "using n-gram tokenizer: min_order({0}) max_order({1})".format(min_order,max_order)
  if args.term_freq:
    print "counting term frequency"
  else:
    print "counting document frequency"
  b_dirs = build_index(items, tokenizer, buckets_dir, args.buckets, args.jobs, args.chunksize, args.sample_count, args.sample_size, args.term_freq, args.line)

  # output the paths to the buckets
  with open(bucketlist_path,'w') as f:
    for d in b_dirs:
      f.write(d+'\n')


########NEW FILE########
__FILENAME__ = train
#!/usr/bin/env python
"""
train.py - 
All-in-one tool for easy training of a model for langid.py. This depends on the
training tools for individual steps, which can be run separately.

Marco Lui, January 2013

Copyright 2013 Marco Lui <saffsd@gmail.com>. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the
authors and should not be interpreted as representing official policies, either expressed
or implied, of the copyright holder.
"""

TRAIN_PROP = 1.0 # probability than any given document is selected
MIN_DOMAIN = 1 # minimum number of domains a language must be present in to be included
MAX_NGRAM_ORDER = 4 # largest order of n-grams to consider
TOP_DOC_FREQ = 15000 # number of tokens to consider for each order
NUM_BUCKETS = 64 # number of buckets to use in k-v pair generation
CHUNKSIZE = 50 # maximum size of chunk (number of files tokenized - less = less memory use)
FEATURES_PER_LANG = 300 # number of features to select for each language

import argparse
import os, csv
import numpy
import base64, bz2, cPickle
import shutil

from common import makedir, write_weights, write_features, read_weights, read_features
from index import CorpusIndexer
from tokenize import build_index, NGramTokenizer
from DFfeatureselect import tally, ngram_select
from IGweight import compute_IG
from LDfeatureselect import select_LD_features
from scanner import build_scanner, Scanner
from NBtrain import learn_nb_params

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-p","--proportion", type=float, help="proportion of training data to use", default=TRAIN_PROP)
  parser.add_argument("-m","--model", help="save output to MODEL_DIR", metavar="MODEL_DIR")
  parser.add_argument("-j","--jobs", type=int, metavar='N', help="spawn N processes (set to 1 for no paralleization)")
  parser.add_argument("-t", "--temp", metavar='TEMP_DIR', help="store buckets in TEMP_DIR instead of in MODEL_DIR/buckets")
  parser.add_argument("-d","--domain", metavar="DOMAIN", action='append',
      help="use DOMAIN - can be specified multiple times (uses all domains found if not specified)")
  parser.add_argument("-l","--lang", metavar="LANG", action='append',
      help="use LANG - can be specified multiple times (uses all langs found if not specified)")
  parser.add_argument("--min_domain", type=int, help="minimum number of domains a language must be present in", default=MIN_DOMAIN)
  parser.add_argument("--buckets", type=int, metavar='N', help="distribute features into N buckets", default=NUM_BUCKETS)
  parser.add_argument("--max_order", type=int, help="highest n-gram order to use", default=MAX_NGRAM_ORDER)
  parser.add_argument("--chunksize", type=int, help="max chunk size (number of files to tokenize at a time - smaller should reduce memory use)", default=CHUNKSIZE)
  parser.add_argument("--df_tokens", type=int, help="number of tokens to consider for each n-gram order", default=TOP_DOC_FREQ)
  parser.add_argument("--word", action='store_true', default=False, help="use 'word' tokenization (currently str.split)")
  parser.add_argument("--df_feats", metavar="FEATS", help="Instead of DF feature selection, use a list of features from FEATS")
  parser.add_argument("--ld_feats", metavar="FEATS", help="Instead of LD feature selection, use a list of features from FEATS")
  parser.add_argument("--feats_per_lang", type=int, metavar='N', help="select top N features for each language", default=FEATURES_PER_LANG)
  parser.add_argument("--no_domain_ig", action="store_true", default=False, help="use only per-langugage IG in LD calculation")
  parser.add_argument("--debug", action="store_true", default=False, help="produce debug output (all intermediates)")
  parser.add_argument("--line", action="store_true", help="treat each line in a file as a document")

  group = parser.add_argument_group('sampling')
  group.add_argument("--sample_size", type=int, help="size of sample for sampling-based tokenization", default=140)
  group.add_argument("--sample_count", type=int, help="number of samples for sampling-based tokenization", default=None)

  parser.add_argument("corpus", help="read corpus from CORPUS_DIR", metavar="CORPUS_DIR")

  args = parser.parse_args()

  if args.sample_count and args.line:
    parser.error("sampling in line mode is not implemented")

  if args.df_feats and args.ld_feats:
    parser.error("--df_feats and --ld_feats are mutually exclusive")

  corpus_name = os.path.basename(args.corpus)
  if args.model:
    model_dir = args.model
  else:
    model_dir = os.path.join('.', corpus_name+'.model')

  makedir(model_dir)

  # display paths
  print "corpus path:", args.corpus
  print "model path:", model_dir

  indexer = CorpusIndexer(args.corpus, min_domain=args.min_domain, proportion=args.proportion,
                          langs = args.lang, domains = args.domain, line_level=args.line)

  # Compute mappings between files, languages and domains
  lang_dist = indexer.dist_lang
  lang_index = indexer.lang_index
  lang_info = ' '.join(("{0}({1})".format(k, lang_dist[v]) for k,v in lang_index.items()))
  print "langs({0}): {1}".format(len(lang_dist), lang_info)

  domain_dist = indexer.dist_domain
  domain_index = indexer.domain_index
  domain_info = ' '.join(("{0}({1})".format(k, domain_dist[v]) for k,v in domain_index.items()))
  print "domains({0}): {1}".format(len(domain_dist), domain_info)

  print "identified {0} documents".format(len(indexer.items))

  if args.line:
  	print "treating each LINE as a document"

  items = sorted(set( (d,l,p) for (d,l,n,p) in indexer.items ))
  if args.debug:
    langs_path = os.path.join(model_dir, 'lang_index')
    domains_path = os.path.join(model_dir, 'domain_index')
    index_path = os.path.join(model_dir, 'paths')

    # output the language index
    with open(langs_path,'w') as f:
      writer = csv.writer(f)
      writer.writerows((l, lang_dist[lang_index[l]]) 
          for l in sorted(lang_index, key=lang_index.get))

    # output the domain index
    with open(domains_path,'w') as f:
      writer = csv.writer(f)
      writer.writerows((d, domain_dist[domain_index[d]]) 
          for d in sorted(domain_index, key=domain_index.get))

    # output items found
    with open(index_path,'w') as f:
      writer = csv.writer(f)
      writer.writerows(items)

  if args.temp:
    buckets_dir = args.temp
  else:
    buckets_dir = os.path.join(model_dir, 'buckets')
  makedir(buckets_dir)


  if args.ld_feats:
    # LD features are pre-specified. We are basically just building the NB model.
    LDfeats = read_features(args.ld_feats)

  else:
    # LD features not pre-specified, so we compute them.

    # Tokenize
    DFfeats = None
    print "will tokenize %d documents" % len(items)
    # TODO: Custom tokenizer if doing custom first-pass features
    if args.df_feats:
      print "reading custom features from:", args.df_feats
      DFfeats = read_features(args.df_feats)
      print "building tokenizer for custom list of {0} features".format(len(DFfeats))
      tk = Scanner(DFfeats)
    elif args.word:
      print "using word tokenizer"
      tk = str.split
    else:
      print "using byte NGram tokenizer, max_order: {0}".format(args.max_order)
      tk = NGramTokenizer(1, args.max_order)
    
    # First-pass tokenization, used to determine DF of features
    tk_dir = os.path.join(buckets_dir, 'tokenize-pass1')
    makedir(tk_dir)
    b_dirs = build_index(items, tk, tk_dir, args.buckets, args.jobs, args.chunksize, args.sample_count, args.sample_size, args.line)

    if args.debug:
      # output the paths to the buckets
      bucketlist_path = os.path.join(model_dir, 'bucketlist')
      with open(bucketlist_path,'w') as f:
        for d in b_dirs:
          f.write(d+'\n')

    # We need to compute a tally if we are selecting features by DF, but also if
    # we want full debug output.
    if DFfeats is None or args.debug:
      # Compute DF per-feature
      doc_count = tally(b_dirs, args.jobs)
      if args.debug:
        doc_count_path = os.path.join(model_dir, 'DF_all')
        write_weights(doc_count, doc_count_path)
        print "wrote DF counts for all features to:", doc_count_path

    if DFfeats is None:
      # Choose the first-stage features
      DFfeats = ngram_select(doc_count, args.max_order, args.df_tokens)

    if args.debug:
      feature_path = os.path.join(model_dir, 'DFfeats')
      write_features(DFfeats, feature_path)
      print 'wrote features to "%s"' % feature_path 

    # Dispose of the first-pass tokenize output as it is no longer 
    # needed.
    if not args.debug:
      shutil.rmtree(tk_dir)

    # Second-pass tokenization to only obtain counts for the selected features.
    # As the first-pass set is typically much larger than the second pass, it often 
    # works out to be faster to retokenize the raw documents rather than iterate
    # over the first-pass counts.
    DF_scanner = Scanner(DFfeats)
    df_dir = os.path.join(buckets_dir, 'tokenize-pass2')
    makedir(df_dir)
    b_dirs = build_index(items, DF_scanner, df_dir, args.buckets, args.jobs, args.chunksize)
    b_dirs = [[d] for d in b_dirs]

    # Build vectors of domain and language distributions for use in IG calculation
    domain_dist_vec = numpy.array([ domain_dist[domain_index[d]]
            for d in sorted(domain_index, key=domain_index.get)], dtype=int)
    lang_dist_vec = numpy.array([ lang_dist[lang_index[l]]
            for l in sorted(lang_index.keys(), key=lang_index.get)], dtype=int)

    # Compute IG
    ig_params = [
      ('lang', lang_dist_vec, '.lang', True),
    ]
    if not args.no_domain_ig:
      ig_params.append( ('domain', domain_dist_vec, '.domain', False) )

    ig_vals = {}
    for label, dist, suffix, binarize in ig_params:
      print "Computing information gain for {0}".format(label)
      ig = compute_IG(b_dirs, DFfeats, dist, binarize, suffix, args.jobs)
      if args.debug:
        weights_path = os.path.join(model_dir, 'IGweights' + suffix + ('.bin' if binarize else ''))
        write_weights(ig, weights_path)
      ig_vals[label] = dict((row[0], numpy.array(row[1].flat)) for row in ig)

    # Select features according to the LD criteria
    features_per_lang = select_LD_features(ig_vals['lang'], ig_vals.get('domain'), args.feats_per_lang, ignore_domain = args.no_domain_ig)
    LDfeats = reduce(set.union, map(set, features_per_lang.values()))
    print 'selected %d features' % len(LDfeats)

    if args.debug:
      feature_path = os.path.join(model_dir, 'LDfeats')
      write_features(sorted(LDfeats), feature_path)
      print 'wrote LD features to "%s"' % feature_path 

      with open(feature_path + '.perlang', 'w') as f:
        writer = csv.writer(f)
        for i in range(len(features_per_lang)):
          writer.writerow(map(repr,features_per_lang[i]))
      print 'wrote LD.perlang features to "%s"' % feature_path + '.perlang'

  # Compile a scanner for the LDfeats
  tk_nextmove, tk_output = build_scanner(LDfeats)
  if args.debug:
    scanner_path = feature_path + '.scanner'
    with open(scanner_path, 'w') as f:
      cPickle.dump((tk_nextmove, tk_output, LDfeats), f)
    print "wrote scanner to {0}".format(scanner_path)

  # Assemble the NB model
  langs = sorted(lang_index, key=lang_index.get)

  nb_classes = langs
  nb_dir = os.path.join(buckets_dir, 'NBtrain')
  makedir(nb_dir)
  nb_pc, nb_ptc = learn_nb_params([(int(l),p) for _, l, p in items], len(langs), tk_nextmove, tk_output, nb_dir, args)

  # output the model
  output_path = os.path.join(model_dir, 'model')
  model = nb_ptc, nb_pc, nb_classes, tk_nextmove, tk_output
  string = base64.b64encode(bz2.compress(cPickle.dumps(model)))
  with open(output_path, 'w') as f:
    f.write(string)
  print "wrote model to %s (%d bytes)" % (output_path, len(string))

  # remove buckets if debug is off. We don't generate buckets if ldfeats is supplied.
  if not args.debug and not args.ld_feats:
    shutil.rmtree(df_dir)
    if not args.temp:
      # Do not remove the buckets dir if temp was supplied as we don't know
      # if we created it.
      shutil.rmtree(buckets_dir)
    


########NEW FILE########