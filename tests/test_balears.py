import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from balears import consume,NS,TOMBSTONES,VERSIONS

class BalearFeedTests(unittest.TestCase):
 def setUp(self):TOMBSTONES.clear();VERSIONS.clear();self.state={};self.orgs={'123':{'name':'Organisme de prova'}}
 def feed(self,lots=('1','2'),date='2026-09-01T10:00:00Z'):
  header='<feed xmlns="'+NS['a']+'" xmlns:cbc="'+NS['b']+'" xmlns:cac="'+NS['c']+'" xmlns:ep="'+NS['e']+'" xmlns:eb="'+NS['x']+'">'
  lotxml=''.join('<cac:ProcurementProjectLot><cbc:ID>'+n+'</cbc:ID><cac:ProcurementProject><cbc:Name>Lot '+n+'</cbc:Name><cac:BudgetAmount><cbc:TaxExclusiveAmount>1000</cbc:TaxExclusiveAmount></cac:BudgetAmount></cac:ProcurementProject></cac:ProcurementProjectLot>' for n in lots)
  return (header+'<entry><id>https://example.org/entry/42</id><updated>'+date+'</updated><title>Programari</title><link href="https://example.org/tender"/><ep:ContractFolderStatus><cbc:ContractFolderID>EXP-1</cbc:ContractFolderID><eb:ContractFolderStatusCode>ADJ</eb:ContractFolderStatusCode><ep:LocatedContractingParty><cac:Party><cac:PartyIdentification><cbc:ID schemeName="ID_PLATAFORMA">123</cbc:ID></cac:PartyIdentification></cac:Party></ep:LocatedContractingParty><cac:ProcurementProject><cbc:Name>Software</cbc:Name><cac:RequiredCommodityClassification><cbc:ItemClassificationCode>72000000</cbc:ItemClassificationCode></cac:RequiredCommodityClassification></cac:ProcurementProject>'+lotxml+'<cac:TenderResult><cac:WinningParty><cac:PartyName><cbc:Name>Empresa de prova</cbc:Name></cac:PartyName></cac:WinningParty><cac:AwardedTenderedProject><cbc:ProcurementProjectLotID>1</cbc:ProcurementProjectLotID><cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount>800</cbc:TaxExclusiveAmount></cac:LegalMonetaryTotal></cac:AwardedTenderedProject></cac:TenderResult></ep:ContractFolderStatus></entry></feed>').encode()
 def test_award_is_not_copied_to_other_lots(self):
  consume(self.feed(),self.orgs,self.state);rows={r['lot']:r for r in self.state.values()};self.assertEqual(rows['1']['awarded'],800);self.assertIsNone(rows['2']['awarded']);self.assertEqual(rows['2']['winner'],'')
 def test_new_snapshot_removes_old_lot_and_old_replay_cannot_restore_it(self):
  consume(self.feed(),self.orgs,self.state);consume(self.feed(('1',),'2026-09-02T10:00:00Z'),self.orgs,self.state);consume(self.feed(),self.orgs,self.state);self.assertEqual(len(self.state),1)
 def test_tombstone_survives_old_replay(self):
  consume(self.feed(),self.orgs,self.state);consume(b'<feed xmlns="http://www.w3.org/2005/Atom"><at:deleted-entry ref="https://example.org/entry/42" when="2026-09-03T10:00:00Z"/></feed>',self.orgs,self.state);consume(self.feed(),self.orgs,self.state);self.assertFalse(self.state)
