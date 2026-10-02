import { test } from "node:test";
import assert from "node:assert/strict";
import { SetPlayer } from "../app/static/player.js";
global.window = { location: { origin:"https://nextset.test" } };
global.document = { createElement: () => ({}) };
const tick = () => new Promise(resolve=>setTimeout(resolve,0));
function setup(timeout=100) {
  const instances=[], statuses=[];
  const YT={PlayerState:{CUED:5},Player:class {
    constructor(node,options){this.options=options;this.cues=[];this.destroyed=false;instances.push(this);}
    cueVideoById(value){this.cues.push(value);}
    destroy(){this.destroyed=true;}
  }};
  const container={replaceChildren(){},append(){}};
  return {instances,statuses,player:new SetPlayer(container,s=>statuses.push(s),async()=>YT,timeout)};
}
test("cue only, replacement destroys previous and ignores late callbacks, no next at ENDED",async()=>{
  const {player,instances,statuses}=setup();
  const first=player.replace("AbCdEf12345",1); await tick();
  const a=instances[0]; a.options.events.onReady({target:a});
  assert.deepEqual(a.cues,[{videoId:"AbCdEf12345",startSeconds:0}]);
  assert.equal(a.options.playerVars.autoplay,0);
  a.options.events.onStateChange({data:5}); assert.equal(await first,"ready");
  const second=player.replace("ZbCdEf12345",2); await tick();
  assert.equal(a.destroyed,true);
  const previous=statuses.length;
  a.options.events.onError({data:100}); a.options.events.onReady({target:a});
  assert.equal(statuses.length,previous); assert.equal(a.cues.length,1);
  const b=instances[1]; b.options.events.onReady({target:b}); b.options.events.onStateChange({data:5});
  assert.equal(await second,"ready");
  b.options.events.onStateChange({data:0}); assert.equal(instances.length,2);
  player.clear(3);
});
test("error, timeout and canceled loads resolve and permit another choice",async()=>{
  const {player,instances,statuses}=setup(15);
  const first=player.replace("AbCdEf12345",1); await tick();
  instances[0].options.events.onError({data:153}); assert.equal(await first,"error");
  assert.match(statuses.at(-1).message,/identificare/);
  assert.equal(await player.replace("AbCdEf12345",2),"error");
  const third=player.replace("AbCdEf12345",3);
  player.clear(4); assert.equal(await third,"cancelled");
});
