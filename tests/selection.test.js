import { test } from "node:test";
import assert from "node:assert/strict";
import { catalogOptions, DEFAULT_FILTERS, formatDuration, matchesAllFilters, selectSet } from "../app/static/selection.js";
const item = (id, duration, genres = ["house"], year = 2024) => ({ youtube_id: id, duration_minutes: duration, genres, year });
const catalog = [item("a",59.99),item("b",60),item("c",119.99),item("d",120,["techno","house"],2023)];
test("duration boundaries and AND predicates", () => {
  for (const [duration,expected] of [["lt60",["a"]],["60to120",["b","c"]],["gte120",["d"]]]) {
    assert.deepEqual(catalog.filter(i => matchesAllFilters(i,{...DEFAULT_FILTERS,duration})).map(i=>i.youtube_id),expected);
  }
  assert.equal(selectSet(catalog,{genre:"techno",duration:"gte120",year:2023},null).item.youtube_id,"d");
  assert.equal(selectSet(catalog,{genre:"techno",duration:"gte120",year:2024},null).count,0);
});
test("uniform indexed pool, immediate exclusion only, zero and one result", () => {
  for (let i=0;i<4;i++) assert.equal(selectSet(catalog,DEFAULT_FILTERS,null,()=>i/4).item.youtube_id,catalog[i].youtube_id);
  for (let i=0;i<3;i++) assert.notEqual(selectSet(catalog,DEFAULT_FILTERS,"b",()=>i/3).item.youtube_id,"b");
  assert.equal(selectSet(catalog,DEFAULT_FILTERS,"b",()=>0).item.youtube_id,"a");
  assert.equal(selectSet(catalog,DEFAULT_FILTERS,"a",()=>0).item.youtube_id,"b");
  assert.deepEqual(selectSet([],DEFAULT_FILTERS,null),{count:0,item:null});
  assert.equal(selectSet([catalog[0]],DEFAULT_FILTERS,"a").item,catalog[0]);
});
test("options are deduplicated and sorted; exact duration is formatted", () => {
  assert.deepEqual(catalogOptions(catalog),{genres:["house","techno"],years:[2024,2023]});
  assert.equal(formatDuration(92.5),"1 h 32 min 30 s");
});
test("1000-set filtering and selection budget", () => {
  const large = Array.from({length:1000},(_,i)=>item(String(i),30+i%200,[i%2 ? "house":"techno"],2020+i%5));
  const start = performance.now();
  for (let i=0;i<1000;i++) selectSet(large,{genre:"house",duration:"60to120",year:2021},"1");
  const average=(performance.now()-start)/1000;
  assert.ok(average<100);
  console.log(`1000 records: ${average.toFixed(3)} ms/selection average (1000 iterations)`);
});
