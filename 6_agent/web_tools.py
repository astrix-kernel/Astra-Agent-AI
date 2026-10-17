"""Web access tools — Bing + Wikipedia (no DDG, anti ISP block)."""

import re
import ssl
import json
import urllib.request
import urllib.parse

_ctx = ssl._create_unverified_context()
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'


def _bing_search(query, max_results=5):
    """Bing HTML scraping — a new parser for modern 2024+ format."""

    try:
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&setlang=id&cc=ID"
        req = urllib.request.Request(url, headers={'User-Agent': _UA, 'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8'})
        html = urllib.request.urlopen(req, timeout=15, context=_ctx).read().decode('utf-8', errors='ignore')
        
        results = []
        # Split by b_algo blocks
        blocks = re.split(r'<li class="b_algo"', html)
        
        for block in blocks[1:]:  # first skip (before the first block)
            if len(results) >= max_results:
                break
            
            # Title & URL — Search <h2><a href="...">
            tm = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not tm:
                continue
            href = tm.group(1).replace('&amp;', '&')
            title = re.sub(r'<.*?>', '', tm.group(2)).strip()
            
            # Decode Bing redirect URL (if applicable)
            if 'bing.com/ck/a' in href:
                # Try extracting u parameters (base64 encoded URL)
                um = re.search(r'[?&]u=a1([^&]+)', href)
                if um:
                    try:
                        import base64
                        b64 = um.group(1)
                        # Base64 pad
                        while len(b64) % 4: b64 += '='
                        decoded = base64.urlsafe_b64decode(b64).decode('utf-8', errors='ignore')
                        if decoded.startswith('http'):
                            href = decoded
                    except: pass
            
            # Skip if it's still redirect or not http
            if 'bing.com' in href or not href.startswith('http'):
                # Try looking for cite / visible URL in the block
                cm = re.search(r'<cite[^>]*>([^<]+)</cite>', block)
                if cm:
                    visible = cm.group(1).strip()
                    if not visible.startswith('http'):
                        visible = 'https://' + visible
                    href = visible.split()[0]
                else:
                    continue
            
            # Snippets — search <p class="b_lineclamp..."> or <p> first
            sm = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            if not sm:
                sm = re.search(r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if not sm:
                sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            snippet = re.sub(r'<.*?>', '', sm.group(1)).strip() if sm else ""
            
            results.append(f"[{len(results)+1}] {title}\nURL: {href}\nSnippet: {snippet[:250]}")
        
        return results
    except Exception as e:
        print(f"[Bing error] {e}")
        return []


def _wiki_search(query, max_results=5):
    """Wikipedia API — most stable because of THE OFFICIAL API."""

    try:
        # Try Indonesia first, fallback to English
        for lang in ['id', 'en']:
            url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch=" + urllib.parse.quote(query) + f"&format=json&srlimit={max_results}"
            req = urllib.request.Request(url, headers={'User-Agent': 'AstrixAI/1.0 (Local)'})
            data = json.loads(urllib.request.urlopen(req, timeout=10, context=_ctx).read().decode('utf-8'))
            
            results = []
            for i, item in enumerate(data.get("query", {}).get("search", []), 1):
                title = item.get("title", "")
                snippet = re.sub(r'<.*?>', '', item.get("snippet", "")).strip()
                page_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                results.append(f"[{i}] {title}\nURL: {page_url}\nSnippet: {snippet}")
            
            if results:
                return results
    except Exception as e:
        print(f"[Wiki error] {e}")
    return []


def _duckduckgo_html(query, max_results=5):
    """HTML DDG (last fallback, often blocked in ID)."""

    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={'User-Agent': _UA})
        html = urllib.request.urlopen(req, timeout=10, context=_ctx).read().decode('utf-8', errors='ignore')
        
        results = []
        links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        for i in range(min(len(links), max_results)):
            href = links[i][0]
            title = re.sub(r'<.*?>', '', links[i][1]).strip()
            snippet = re.sub(r'<.*?>', '', snippets[i]).strip() if i < len(snippets) else ""
            
            if "uddg=" in href:
                m = re.search(r'uddg=([^&]+)', href)
                if m: href = urllib.parse.unquote(m.group(1))
            
            if not href.startswith('http'):
                continue
            
            results.append(f"[{len(results)+1}] {title}\nURL: {href}\nSnippet: {snippet[:250]}")
        
        return results
    except Exception as e:
        print(f"[DDG error] {e}")
        return []


def web_search(query, max_results=5):
    """Search the internet-try Bing, then Wikipedia, then DDG."""

    # Bing first (most likely work on ID)
    results = _bing_search(query, max_results)
    if results:
        return f"🔍 Hasil pencarian '{query}' (via Bing):\n\n" + "\n\n".join(results)
    
    # Wikipedia fallback (most stable, but article-based)
    results = _wiki_search(query, max_results)
    if results:
        return f"🔍 Hasil Wikipedia untuk '{query}':\n\n" + "\n\n".join(results)
    
    # DDG last resort
    results = _duckduckgo_html(query, max_results)
    if results:
        return f"🔍 Hasil pencarian '{query}':\n\n" + "\n\n".join(results)
    
    return f"❌ Semua mesin pencari gagal untuk '{query}'. Coba browse_url langsung ke sumber."


def browse_url(url):
    """Open & read the contents of the web page."""

    try:
        req = urllib.request.Request(url, headers={'User-Agent': _UA, 'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8'})
        html = urllib.request.urlopen(req, timeout=20, context=_ctx).read().decode('utf-8', errors='ignore')
        
        html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<nav.*?</nav>', '', html, flags=re.DOTALL)
        html = re.sub(r'<footer.*?</footer>', '', html, flags=re.DOTALL)
        
        text = re.sub(r'<.*?>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return f"📄 Isi halaman {url}:\n\n{text[:5000]}{'...' if len(text) > 5000 else ''}"
    except Exception as e:
        return f"❌ Browse error: {e}"
