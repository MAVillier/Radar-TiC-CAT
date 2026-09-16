import assert from 'node:assert/strict';
import {madridTime,stage,countdown,dossierModel,criteriaType,safeUrl,durationLabel,sourceTime,compareDeadline} from '../site/core.js';
const now=Date.parse('2026-09-08T12:00:00Z');
assert.equal(madridTime('2026-09-08T14:00:00'),now);
assert.equal(madridTime('2026-01-08T14:00:00'),Date.parse('2026-01-08T13:00:00Z'));
assert.ok(Number.isNaN(madridTime('2026-09-08')));
const r={phase:'Anunci de licitació',deadline:'2026-09-09T14:00:00',budget:100};
assert.equal(stage(r,now),'open');assert.equal(countdown(r,now).number,1);
assert.equal(stage(r,now+864e5),'pending');
assert.equal(stage({...r,title:'[EN SUSPENSIÓ] Cloud'},now),'suspended');
assert.equal(stage({...r,isSystem:true},now),'system');
assert.equal(stage({...r,phase:'Adjudicació'},now),'awarded');
assert.equal(criteriaType({kind:'automatic',label:'Certificació tècnica'}),'automatic');
assert.equal(dossierModel(r,{terms:{}},{economicRows:[{label:'Pròrrogues',amount:50}]}).extension,null);
assert.equal(dossierModel(r,{singleLot:true,terms:{extensionAllowed:false}},{economicRows:[{label:'Pròrrogues',amount:50}]}).extension,null);
assert.equal(dossierModel(r,{singleLot:true,terms:{}},{economicRows:[{label:'Pròrrogues',amount:50}]}).withExtensions,null);
assert.equal(safeUrl('javascript:alert(1)'),'#');
console.log('Core: terminis Madrid, fases, suspensió, criteris i imports per lot correctes');

const row={...r,rawHash:'revision-1'};
const verified={validation:{recordHash:'revision-1',fields:{extensionAllowed:true,extensionAmount:50}}};
assert.equal(dossierModel(row,{},verified).withExtensions,150);
assert.equal(dossierModel({...row,rawHash:'revision-2'},{},verified).extension,null);
assert.equal(dossierModel(row,{}, {validation:{recordHash:'revision-1',fields:{extensionAllowed:false}}}).extension,0);
const duration=durationLabel('2026-12-31T23:00:00.000Z — 2027-12-30T23:00:00.000Z');
assert.match(duration,/1 de gen.*2027/);assert.match(duration,/31 de des.*2027/);assert.doesNotMatch(duration,/:|T23/);
assert.equal(sourceTime({sourcesUpdated:{a:'2026-09-13T10:00:00Z',b:'2026-09-13T11:00:00Z'}}),Date.parse('2026-09-13T10:00:00Z'));
const official={recordHash:'revision-1',terms:{extensionAllowed:true,extensionText:'Dues pròrrogues de dotze mesos'}};
assert.equal(dossierModel(row,official,{}).d.terms.extensionText,official.terms.extensionText);
assert.equal(dossierModel({...row,rawHash:'revision-2'},official,{}).d.terms.extensionAllowed,null);
assert.equal(dossierModel(row,official,{validation:{recordHash:'revision-1',fields:{},conflicts:['extensionAllowed']}}).d.terms.extensionAllowed,null);

// Both directions use precise deadlines; records without an active deadline stay last.
const soon={...r,deadline:'2026-09-09T14:00:00',published:'2026-09-01'},later={...r,deadline:'2026-09-20T14:00:00',published:'2026-09-02'},missing={...r,deadline:null};
assert.deepEqual([missing,later,soon].sort((a,b)=>compareDeadline(a,b,'asc',now)),[soon,later,missing]);
assert.deepEqual([missing,soon,later].sort((a,b)=>compareDeadline(a,b,'desc',now)),[later,soon,missing]);
assert.equal(compareDeadline(missing,missing,'desc',now),0);
assert.ok(compareDeadline(soon,{...soon,phase:'Adjudicació'},'desc',now)<0);
