import unittest,sys,json,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from document_validation import extract,resolve

class ContractTermsTests(unittest.TestCase):
 def docs(self):
  fixtures=json.loads((pathlib.Path(__file__).parent/'fixtures/cyber_terms.json').read_text(encoding='utf-8'))
  return [dict(url=d['url'],sha256=d['sha256'],status='read',evidence=extract([(p['page'],p['text'],p['layout']) for p in d['pages']])) for d in fixtures]
 def test_real_pcap_and_memory_independently_produce_same_breakdown(self):
  for doc in self.docs():
   with self.subTest(document=doc['url']):
    result=resolve({'rawHash':'r','budget':479338.74,'vec':1533883.97},{'singleLot':True},[doc],{})
    f=result['fields'];self.assertEqual(f['extensionCount'],2);self.assertEqual(f['extensionMonthsEach'],12)
    self.assertEqual(f['extensionAmount'],958677.48);self.assertEqual(f['modificationAmount'],95867.75)
    self.assertEqual(result['conflicts'],[])
 def test_repeated_table_is_not_counted_twice(self):
  doc=self.docs()[0];doc['evidence']*=2
  f=resolve({'rawHash':'r','budget':479338.74,'vec':1533883.97},{'singleLot':True},[doc],{})['fields']
  self.assertEqual(f['extensionAmount'],958677.48)
 def test_multi_lot_contract_does_not_inherit_unscoped_amounts(self):
  result=resolve({'rawHash':'r','lot':'2','budget':479338.74,'vec':1533883.97},{'singleLot':False},self.docs(),{})
  self.assertNotIn('extensionAmount',result['fields'])
 def test_vec_difference_is_not_used_to_invent_extensions(self):
  result=resolve({'rawHash':'r','budget':100,'vec':320},{'singleLot':True},[],{})
  self.assertNotIn('extensionAmount',result['fields'])
 def test_inconsistent_financial_table_is_not_published(self):
  result=resolve({'rawHash':'r','budget':479338.74,'vec':999999},{'singleLot':True},self.docs(),{})
  self.assertIn('economicBreakdown',result['conflicts']);self.assertNotIn('extensionAmount',result['fields'])
