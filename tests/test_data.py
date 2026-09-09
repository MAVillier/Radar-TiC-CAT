import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from refresh import number,discount,identity,normalize,candidates
from enrich import extract
from sda import parent_reference

class DataTests(unittest.TestCase):
    def test_sda_reference_at_contract_level(self):
        parent,path=parent_reference({'dadesBasiquesPublicacio':{'codiExpedientReferencia':'CTTI-2025-96'}},{})
        self.assertEqual(parent,'CTTI-2025-96')
        self.assertIn('dadesBasiquesPublicacio',path)
    def test_sda_unrelated_reference_not_promoted(self):
        self.assertEqual(parent_reference({}, {'codiExpedientReferencia':'CTTI-2024-1'}),(None,None))
    def test_discount(self):
        self.assertEqual(discount('45000','35990.00')['value'],20.02)
        self.assertEqual(discount('100','0')['value'],100)
        self.assertEqual(discount('100','100')['value'],0)
    def test_reject_unsafe_amounts(self):
        for v in ('20||30','NaN','Infinity','1,234.00','1.234,00','20 euros'):
            self.assertIsNone(number(v))
        self.assertIsNone(discount('0','20')['value'])
        self.assertIsNone(discount('100','110')['value'])
        self.assertIsNone(discount('100','50',multi=True)['value'])
    def test_identity_includes_organ_and_lot(self):
        a={'codi_expedient':'1/2026','codi_organ':'1','numero_lot':'1'}
        self.assertNotEqual(identity(a),identity(a|{'numero_lot':'2'}))
        self.assertNotEqual(identity(a),identity(a|{'codi_organ':'2'}))
    def test_no_implicit_expiry(self):
        r=normalize({'durada_contracte':'2 anys','data_formalitzacio_contracte':'2024-01-01'})
        self.assertIsNone(r['endDate'])
    def test_explicit_expiry(self):
        self.assertEqual(normalize({'durada_contracte':'12/09/2023 a 11/09/2026'})['endDate'],'2026-09-11')
    def test_no_lot_guess(self):
        self.assertEqual(extract({'publicacio':{'teLots':True,'dadesPublicacioLot':[{'pressupostLicitacio':10}]}}),[])
    def test_no_winner_name_inference(self):
        out=extract({'publicacio':{'teLots':False,'dadesPublicacioLot':[{'identitatEmpresa':[{'empresa':'ABC'}]}]}})
        self.assertEqual(out[0]['companies'],['ABC']);self.assertEqual(out[0]['winners'],[])
    def test_predecessor_not_same_contract_or_future(self):
        base={'id':'a','organCode':'1','exp':'new','phase':'Anunci de licitació','winner':'','awardDate':None,'published':'2026-01-01','title':'plataforma Celonis mineria processos GEEC','description':'','cpv':['72212900-8']}
        old=base|{'id':'b','exp':'old','phase':'Adjudicació','winner':'ABC','awardDate':'2025-01-01'}
        future=old|{'id':'c','awardDate':'2027-01-01'}
        other=old|{'id':'d','organCode':'2'}
        same=old|{'id':'e','exp':'new'}
        rows=[base,old,future,other,same];candidates(rows)
        self.assertEqual([c['id'] for c in base['candidates']],['b'])
if __name__=='__main__':unittest.main()
