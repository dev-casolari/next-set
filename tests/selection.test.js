import { test } from "node:test";
import assert from "node:assert/strict";
import { catalogOptions, DEFAULT_FILTERS, formatDuration, matchesAllFilters, normalizeApproxDuration, selectSet } from "../app/static/selection.js";
const item = (id, duration, genres = ["house"], year = 2024, durationApprox = null) => ({ youtube_id: id, duration_minutes: duration, duration_approx: durationApprox, genres, year });
const catalog = [item("a",59.99,["house"],2024,"30min"),item("b",60,["house"],2024,"1h"),item("c",119.99,["house"],2024,"1h 30min"),item("d",120,["techno","house"],2023,"2h")];
test("exact approximate-duration filtering and AND predicates", () => {
  for (const [duration,expected] of [["30min",["a"]],["1h",["b"]],["1h 30min",["c"]],["2h",["d"]]]) {
    assert.deepEqual(catalog.filter(i => matchesAllFilters(i,{...DEFAULT_FILTERS,duration})).map(i=>i.youtube_id),expected);
  }
  assert.equal(selectSet(catalog,{genre:"techno",duration:"2h",year:2023},null).item.youtube_id,"d");
  assert.equal(selectSet(catalog,{genre:"techno",duration:"2h",year:2024},null).count,0);
  assert.equal(matchesAllFilters(item("e",90),{...DEFAULT_FILTERS,duration:"all"}),true);
  assert.equal(matchesAllFilters(item("e",90),{...DEFAULT_FILTERS,duration:"1h"}),false);
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
  const options = catalogOptions(catalog);
  assert.deepEqual(options,{genres:["house","techno"],durations:["30min","1h","1h 30min","2h"],years:[2024,2023]});
  assert.deepEqual([...options.genreCounts],[["house",4],["techno",1]]);
  assert.deepEqual([...options.durationCounts],[["30min",1],["1h",1],["1h 30min",1],["2h",1]]);
  assert.deepEqual([...options.yearCounts],[[2024,3],[2023,1]]);
  assert.equal(formatDuration(92.5),"1 h 32 min 30 s");
});
test("duration options deduplicate case and whitespace variants and sort by approximate time", () => {
  const mixed = [
    item("a",60,["house"],2024," 1H  30min "),
    item("b",60,["house"],2024,"30min"),
    item("c",60,["house"],2024,"1h 30MIN"),
    item("d",60,["house"],2024,"1h 30"),
  ];
  assert.deepEqual(catalogOptions(mixed).durations,["30min","1h 30","1H 30min"]);
  assert.equal(normalizeApproxDuration(" 1H   30min "), "1h 30min");
  assert.deepEqual(mixed.map(row => row.duration_approx),[" 1H  30min ","30min","1h 30MIN","1h 30"]);
});
test("genre options keep the first source spelling across case variants", () => {
  const mixedCase = [
    item("a",60,["Tech House","EDM"],2024,"1h"),
    item("b",90,["tech house","edm","Deep House"],2024,"1h"),
    item("c",120,["TECH HOUSE","deep house"],2024,"1h"),
  ];
  const original = structuredClone(mixedCase);
  assert.deepEqual(catalogOptions(mixedCase).genres,["Tech House","Deep House","EDM"]);
  assert.deepEqual(mixedCase,original);
});
test("genre filtering includes all source case variants and still applies other filters", () => {
  const mixedCase = [
    item("a",60,["Tech House"],2024,"1h"),
    item("b",90,["tech house"],2024,"1h"),
    item("c",120,["TECH HOUSE"],2024,"1h"),
    item("d",90,["House"],2024,"1h"),
  ];
  for (const genre of ["Tech House","tech house","TECH HOUSE"]) {
    const filters = {...DEFAULT_FILTERS,genre,duration:"1h"};
    assert.deepEqual(mixedCase.filter(row => matchesAllFilters(row,filters)).map(row => row.youtube_id),["a","b","c"]);
    const selection = selectSet(mixedCase,filters,"a",()=>0);
    assert.equal(selection.count,3);
    assert.equal(selection.item.youtube_id,"b");
  }
  assert.deepEqual(mixedCase.map(row => row.genres[0]),["Tech House","tech house","TECH HOUSE","House"]);
});
test("1000-set filtering and selection budget", () => {
  const large = Array.from({length:1000},(_,i)=>item(String(i),30+i%200,[i%2 ? "house":"techno"],2020+i%5,"1h"));
  const start = performance.now();
  for (let i=0;i<1000;i++) selectSet(large,{genre:"house",duration:"1h",year:2021},"1");
  const average=(performance.now()-start)/1000;
  assert.ok(average<100);
  console.log(`1000 records: ${average.toFixed(3)} ms/selection average (1000 iterations)`);
});
