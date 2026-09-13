import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from document_validation import extract,resolve,candidates
class DocumentValidationTests(unittest.TestCase):
 def test_reads_memory_as_well_as_pcap(self):
  d={'attachments':[{'title':'QC+PCAP.pdf','url':'a'},{'title':'Memoju.pdf','url':'b'}]}
  self.assertEqual(len(candidates(d)),2)
 def test_explicit_extension_is_read(self):
  ev=extract([(2,'Per aquesta contractació s’admet la possibilitat d’un (1) any de pròrroga.')]);self.assertEqual(ev[0]['value'],True)
 def test_conditional_clause_is_not_evidence(self):
  self.assertEqual(extract([(2,'El contracte es podrà prorrogar si així s’ha previst en el quadre.')]),[])
 def test_missing_is_not_no(self):
  self.assertEqual(extract([(1,'Termini inicial de dotze mesos.')]),[])
 def test_scoped_review_requires_same_lot_and_amounts(self):
  r={'lot':'2','budget':46300,'vec':101860,'rawHash':'r'}
  docs=[{'url':'a','status':'read','sha256':'abc'}]
  review={'abc':{'1':{'budget':46300,'vec':101860,'pages':[3],'fields':{'extensionAmount':46300}}}}
  self.assertEqual(resolve(r,{},docs,review)['fields'],{})
 def test_conflicting_documents_do_not_choose_a_value(self):
  docs=[{'url':str(v),'status':'read','sha256':str(v),'evidence':[{'field':'extensionAllowed','value':v,'page':1,'scope':'contract'}]} for v in (True,False)]
  result=resolve({'lot':'2','rawHash':'r'},{},docs,{})
  self.assertNotIn('extensionAllowed',result['fields']);self.assertIn('extensionAllowed',result['conflicts'])
