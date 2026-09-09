"""Contract terms from explicit publication fields, without estimating absent amounts."""
def text(v):
    if isinstance(v,dict):return v.get('text') or v.get('ca') or v.get('es') or ''
    return str(v or '')

def criteria(items):
    return [{'label':text(c.get('criteri') or c.get('descripcioCriteri')),'weight':c.get('ponderacio'),
             'children':[{'label':text(x.get('descripcioCriteri') or x.get('tipusCriteri')),'weight':x.get('puntuacio')} for x in c.get('desglossament',[]) or []]}
            for c in items or []]

def terms(lot,general=None):
    g=general or {};d=lot.get('duradaTermini') or {}
    def field(lk,gk):return lot[lk] if lot.get(lk) is not None else g.get(gk)
    duration=', '.join(str(d[k])+' '+label for k,label in [('anys','anys'),('mesos','mesos'),('dies','dies')] if d.get(k))
    if d.get('iniciTermini') and d.get('fiTermini'):duration=d['iniciTermini']+' — '+d['fiTermini']
    return {'duration':duration or None,'durationMonths':(d.get('anys') or 0)*12+(d.get('mesos') or 0) if duration and not d.get('dies') and not d.get('iniciTermini') else None,
            'extensionAllowed':field('prorroguesPrevistes','preveuenProrroguesAlsPlecs'),
            'extensionText':text(field('informacioProrrogaComplementaria','informacioComplementariaProrroga')),
            'modificationAllowed':field('modificacioPrevista','preveuenModificacionsAlsPlecs'),
            'modificationText':text(field('informacioModificacioComplementaria','informacioComplementariaModificacio')),
            'vec':lot.get('valorEstimat'),'unitPrices':lot.get('preuUnitari'),
            'technicalRequirements':[{'label':text(x.get('criteriSolvencia')),'minimum':text(x.get('valorMinimExigit'))} for x in lot.get('solvenciesTecniques',[]) or []],
            'economicRequirements':[{'label':text(x.get('criteriSolvencia')),'minimum':text(x.get('valorMinimExigit'))} for x in lot.get('solvenciesEconomiques',[]) or []],
            'criteria':criteria(lot.get('criterisAdjudicacio'))}
