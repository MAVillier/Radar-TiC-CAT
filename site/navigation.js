// A single definition keeps visible filters and actual record eligibility aligned.
export const opportunityStates=['open','pending','planned','unknown','suspended'];
export const marketStates=['awarded','closed'];
const allStates=[...opportunityStates,...marketStates,'system'];
export const phaseNames={all:'Tots',open:'En termini',pending:'Pendents d’adjudicació',planned:'Anuncis previs',unknown:'Sense termini publicat',suspended:'Suspeses',awarded:'Adjudicades',closed:'Altres expedients tancats',system:'Adhesió SDA'};
export function phasesFor(view){return view==='home'?['all',...opportunityStates]:view==='awards'?['all',...marketStates]:view==='news'?[]:['all',...allStates];}
export function defaultPhase(view){return view==='home'?'open':view==='awards'?'awarded':'all';}
export function matchesView(view,state,phase){const allowed=phasesFor(view);return allowed.includes(state)&&(phase==='all'||phase===state);}
