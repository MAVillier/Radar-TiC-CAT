import assert from 'node:assert/strict';
import {phasesFor,defaultPhase,matchesView,opportunityStates,marketStates} from '../site/navigation.js';
import {stage} from '../site/core.js';
for(const state of marketStates){assert.equal(matchesView('home',state,'all'),false);assert.ok(!phasesFor('home').includes(state));}
for(const state of opportunityStates){assert.equal(matchesView('awards',state,'all'),false);assert.ok(!phasesFor('awards').includes(state));}
assert.equal(defaultPhase('home'),'open');assert.equal(defaultPhase('awards'),'awarded');
const record={phase:'Anunci de licitació',deadline:'2026-09-25T13:00:00'};
assert.ok(matchesView('home',stage(record,Date.parse('2026-09-24T10:00Z')),'open'));
assert.equal(matchesView('home',stage(record,Date.parse('2026-09-25T11:00Z')),'open'),false);
assert.ok(matchesView('home',stage(record,Date.parse('2026-09-25T11:00Z')),'pending'));
assert.ok(matchesView('awards',stage({...record,phase:'Adjudicació'}),'awarded'));
for(const view of ['saved','sda96','sda129'])for(const state of [...opportunityStates,...marketStates,'system'])assert.ok(matchesView(view,state,'all'));
for(const view of ['home','awards','saved','sda96','sda129'])for(const state of phasesFor(view).filter(s=>s!=='all'))assert.ok(matchesView(view,state,state));
assert.equal(matchesView('home','awarded','awarded'),false); // forged or stale filter
console.log('Navigation: disjoint scopes, matching filters, deadlines and SDA/saved coverage OK.');
