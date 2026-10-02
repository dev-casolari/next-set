"""Deterministic Playwright tests. Run: RUN_BROWSER_TESTS=1 uv run pytest tests/test_browser.py.

External requests are blocked. A local server serves the actual production assets;
only the catalog HTTP response and the YouTube SDK are mocked.
"""
import contextlib
import json
import os
from pathlib import Path
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="Enable RUN_BROWSER_TESTS=1 with Playwright browsers installed")
ROOT = Path(__file__).resolve().parents[1]
ITEMS = [
    {"youtube_id":"AbCdEf12345","title":"House short","genres":["house"],"duration_minutes":59.99,"year":2024},
    {"youtube_id":"BbCdEf12345","title":"House one hour","genres":["house","disco"],"duration_minutes":60,"year":2024},
    {"youtube_id":"CbCdEf12345","title":"Techno two hours","genres":["techno"],"duration_minutes":120,"year":2023},
    {"youtube_id":"DbCdEf12345","title":"House long","genres":["house"],"duration_minutes":119.99,"year":2022},
]
SDK = r"""
window.__players=[]; window.__played=0; window.__autoCue=true;
window.YT={PlayerState:{CUED:5}, Player:class {
  constructor(mount,options){
    this.options=options;this.destroyed=false;this.cues=[];
    this.iframe=document.createElement('iframe');this.iframe.title='YouTube video player';
    mount.replaceWith(this.iframe);window.__players.push(this);
    setTimeout(()=>options.events.onReady({target:this}),0);
  }
  cueVideoById(value){this.cues.push(value); if(window.__autoCue)setTimeout(()=>this.options.events.onStateChange({data:5}),10);}
  playVideo(){window.__played++;}
  loadVideoById(){window.__played++;}
  destroy(){this.destroyed=true;this.iframe.remove();}
}};
window.onYouTubeIframeAPIReady();
"""


@pytest.fixture(scope="module")
def base_url():
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path == "/": self.path = "/static/index.html"
            return super().do_GET()
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(ROOT/"app")))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown();server.server_close();thread.join()


@pytest.fixture
def page(base_url):
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context(viewport={"width":1440,"height":1000})
        page=context.new_page()
        def route(request):
            if request.request.url.startswith(base_url): request.continue_()
            elif request.request.url == "https://www.youtube.com/iframe_api": request.fulfill(body=SDK,content_type="text/javascript")
            else: request.abort()
        page.route("**/*",route)
        page.add_init_script("Math.random = () => 0;")
        yield page
        browser.close()


def open_catalog(page,base_url,items=ITEMS,status=200,error=None):
    calls=[]
    def respond(route):
        calls.append(route.request.url)
        route.fulfill(status=status,json=error or {"fetched_at":"2026-10-01T12:00:00Z","items":items},headers={"Cache-Control":"no-store"})
    page.route("**/api/catalog",respond)
    page.goto(base_url)
    return calls


def test_manual_player_filters_reset_and_single_result(page,base_url):
    calls=open_catalog(page,base_url)
    expect(page.locator("#next")).to_be_enabled()
    expect(page.locator("#set-title")).to_have_text("House short")
    page.locator("#next").click()
    expect(page.locator("#set-title")).to_have_text("House one hour")
    expect(page.locator("#next")).to_be_enabled()
    assert page.evaluate("window.__players[0].destroyed")
    page.select_option("#genre","house")
    page.select_option("#duration","60to120")
    page.select_option("#year","2024")
    expect(page.locator("#set-title")).to_have_text("House one hour")
    expect(page.locator("#selection-note")).to_contain_text("Un solo")
    expect(page.locator("#next")).to_be_disabled()
    before=page.evaluate("window.__players.length")
    page.select_option("#duration","all")
    expect(page.locator("#next")).to_be_enabled()
    page.locator("#reset").click()
    expect(page.locator("#year")).to_have_value("")
    expect(page.locator("#next")).to_be_enabled()
    assert len(calls)==1 and page.evaluate("window.__played")==0
    assert page.evaluate("window.__players.every(p => p.cues.every(c => c.startSeconds === 0))")
    current=page.locator("#set-title").inner_text()
    page.evaluate("window.__players.at(-1).options.events.onStateChange({data:0})")
    expect(page.locator("#set-title")).to_have_text(current)
    page.reload()
    expect(page.locator("#next")).to_be_enabled()
    assert len(calls)==2


def test_no_results_destroys_player_and_reset_recovers(page,base_url):
    open_catalog(page,base_url)
    expect(page.locator("#next")).to_be_enabled()
    page.select_option("#genre","techno")
    page.select_option("#year","2024")
    expect(page.locator("#frame-message-title")).to_have_text("Nessun DJ set corrisponde ai filtri selezionati")
    expect(page.locator("#youtube-player iframe")).to_have_count(0)
    expect(page.locator("#next")).to_be_disabled()
    expect(page.locator("#reset")).to_be_enabled()
    page.locator("#reset").click()
    expect(page.locator("#next")).to_be_enabled()


def test_late_callbacks_do_not_replace_latest_selection_and_error_recovers(page,base_url):
    open_catalog(page,base_url)
    expect(page.locator("#next")).to_be_enabled()
    page.evaluate("window.__old=window.__players[0];window.__autoCue=false")
    page.select_option("#year","2023")
    page.select_option("#year","2022")
    expect(page.locator("#set-title")).to_have_text("House long")
    page.evaluate("window.__old.options.events.onError({data:100});window.__old.options.events.onStateChange({data:5})")
    expect(page.locator("#player-error")).to_be_hidden()
    page.evaluate("window.__players.at(-1).options.events.onError({data:150})")
    expect(page.locator("#player-error")).to_contain_text("non consente")
    page.evaluate("window.__autoCue=true")
    page.locator("#reset").click()
    expect(page.locator("#next")).to_be_enabled()
    expect(page.locator("#player-error")).to_be_hidden()


@pytest.mark.parametrize("status,items,error,title",[(200,[],None,"Catalogo vuoto"),(503,[],{"error":{"code":"CATALOG_RATE_LIMITED"}},"temporaneamente occupato"),(502,[],{"error":{"code":"CATALOG_SCHEMA_INVALID"}},"formato previsto")])
def test_catalog_failure_states(page,base_url,status,items,error,title):
    open_catalog(page,base_url,items,status,error)
    expect(page.locator("#frame-message-title")).to_contain_text(title)
    expect(page.locator("#reload")).to_be_visible()
    expect(page.locator("#next")).to_be_disabled()
    expect(page.locator("#genre")).to_be_disabled()


@pytest.mark.parametrize("width",[320,390,768,1440])
def test_responsive_layout_and_plain_text_titles(page,base_url,width):
    page.set_viewport_size({"width":width,"height":1000})
    items=[{**ITEMS[0],"title":"<img src=x onerror=alert(1)> " + "Titolo molto lungo "*15}]
    open_catalog(page,base_url,items)
    expect(page.locator("#set-title")).to_contain_text("<img src=x")
    expect(page.locator("#set-title img")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.locator("#player-frame").bounding_box()["height"] >= 200
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()


def test_bfcache_resets_filters_and_rereads_catalog(page,base_url):
    calls=open_catalog(page,base_url)
    expect(page.locator("#next")).to_be_enabled()
    page.select_option("#genre","house")
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
    expect(page.locator("#genre")).to_have_value("")
    expect(page.locator("#next")).to_be_enabled()
    assert len(calls)==2


def test_webmcp_uses_same_state_and_rejects_invalid_filter(page,base_url):
    page.add_init_script("window.__tools={};Object.defineProperty(document,'modelContext',{value:{registerTool(t){window.__tools[t.name]=t}}})")
    open_catalog(page,base_url)
    expect(page.locator("#next")).to_be_enabled()
    result=page.evaluate("window.__tools.nextset_select_set.execute({genre:'techno',year:2023})")
    assert result["candidates"]==1 and result["current"]["title"]=="Techno two hours"
    expect(page.locator("#genre")).to_have_value("techno")
    assert page.evaluate("window.__tools.nextset_get_selection.execute({}).filters.year")==2023
    assert page.evaluate("window.__tools.nextset_select_set.execute({genre:'invalid'}).then(()=>false,()=>true)")
    expect(page.locator("#genre")).to_have_value("techno")


def test_browser_performance_1000_sets(page,base_url):
    open_catalog(page,base_url)
    result=page.evaluate("""async()=>{
      const {selectSet}=await import('/static/selection.js');
      const items=Array.from({length:1000},(_,i)=>({youtube_id:String(i),genres:['house'],duration_minutes:30+i%200,year:2024}));
      const start=performance.now();
      for(let i=0;i<1000;i++) selectSet(items,{genre:'house',duration:'60to120',year:2024},null);
      return (performance.now()-start)/1000;
    }""")
    print(f"Chromium {page.context.browser.version}: {result:.3f} ms per selection on 1000 records")
    assert result<100
