import asyncio
import threading

import pytest
from aiohttp import web


class MockTalenta:
    """Minimal stand-in for Mekari SSO + Talenta dashboard + action endpoint."""

    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/users/sign_in", self._login_page)
        self.app.router.add_post("/users/sign_in", self._do_login)
        self.app.router.add_get("/", self._dashboard)
        self.app.router.add_get("/live-attendance", self._live_attendance)
        self.app.router.add_post("/api/clock-in", self._do_clock_in)
        self.calls: list = []
        self.clock_in_recorded = False

    async def _login_page(self, request):
        return web.Response(
            text="""
            <html><body>
              <form method='post' action='/users/sign_in'>
                <input name='user[email]'/>
                <input name='user[password]' type='password'/>
                <button type='submit'>Sign in</button>
              </form>
            </body></html>
            """,
            content_type="text/html",
        )

    async def _do_login(self, request):
        data = await request.post()
        if data.get("user[email]") and data.get("user[password]"):
            resp = web.HTTPFound("/")
            resp.set_cookie("session", "ok")
            return resp
        return web.Response(
            status=401,
            text="<div class='alert-danger'>bad credentials</div>",
            content_type="text/html",
        )

    async def _dashboard(self, request):
        if request.cookies.get("session") != "ok":
            return web.HTTPFound("/users/sign_in")
        return web.Response(
            text="<html><body>dashboard</body></html>", content_type="text/html"
        )

    async def _live_attendance(self, request):
        if request.cookies.get("session") != "ok":
            return web.HTTPFound("/users/sign_in")
        time_html = (
            "<div data-testid='clock-in-time'>08:07</div>"
            if self.clock_in_recorded
            else ""
        )
        click_script = (
            "fetch('/api/clock-in',{method:'POST'})"
            ".then(()=>document.body.innerHTML+="
            "'<div class=toast-success>ok</div>')"
        )
        return web.Response(
            text=f"""
            <html><body>
              <div data-testid='today-attendance-card'>{time_html}</div>
              <button onclick="{click_script}">Clock In</button>
            </body></html>
            """,
            content_type="text/html",
        )

    async def _do_clock_in(self, request):
        self.calls.append(("clock-in", await request.text()))
        self.clock_in_recorded = True
        return web.json_response({"ok": True})


@pytest.fixture
def mock_talenta():
    server = MockTalenta()

    loop = asyncio.new_event_loop()
    runner = web.AppRunner(server.app)
    site_holder: dict = {}

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", 0)
        loop.run_until_complete(site.start())
        site_holder["port"] = site._server.sockets[0].getsockname()[1]
        loop.run_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    while "port" not in site_holder:
        pass

    base = f"http://127.0.0.1:{site_holder['port']}"
    try:
        yield server, base
    finally:
        loop.call_soon_threadsafe(loop.stop)
