from dataclasses import asdict
from typing import Any, Dict, Optional

from agent_trader.account_sync import sync_account_state
from agent_trader.audit_log import append_audit_event
from agent_trader.config import Settings, load_settings
from agent_trader.control_state import read_control_state
from agent_trader.execution_service import execute_trade_proposal
from agent_trader.hbot_client import HummingbotClient, UrllibTransport
from agent_trader.models import AccountState, RiskLimits, StrategySignal, TradeProposal
from agent_trader.okx_account_sync import sync_okx_account_state
from agent_trader.okx_client import OKXClient, OKXCredentials
from agent_trader.okx_execution_service import execute_okx_trade_proposal
from agent_trader.okx_ws import OKXWebSocketClient
from agent_trader.proposal_service import build_trade_proposal
from agent_trader.reconcile_job import reconcile_open_orders_job
from agent_trader.risk import evaluate_trade
from agent_trader.signal_security import ensure_signal_not_duplicate, verify_signal_auth
from agent_trader.web_ui import read_recent_audit_events, summarize_events
from agent_trader.control_state import halt_trading, read_control_state, resume_trading


def _apply_control_state(resolved: Settings) -> RiskLimits:
    base = resolved.risk_limits
    state = read_control_state(resolved.control_state_path)
    if not state.trading_halted or base.trading_halted:
        return base
    return RiskLimits(
        max_notional_usd=base.max_notional_usd,
        max_leverage=base.max_leverage,
        daily_loss_limit_pct=base.daily_loss_limit_pct,
        max_slippage_bps=base.max_slippage_bps,
        min_equity_usd=base.min_equity_usd,
        trading_halted=True,
    )

settings = load_settings()



def get_settings() -> Settings:
    return settings



def make_hbot_client(current_settings: Optional[Settings] = None) -> HummingbotClient:
    resolved = current_settings or get_settings()
    transport = UrllibTransport(
        base_url=resolved.hbot_api_url,
        username=resolved.hbot_api_username,
        password=resolved.hbot_api_password,
    )
    return HummingbotClient(transport)



def make_okx_client(current_settings: Optional[Settings] = None) -> OKXClient:
    resolved = current_settings or get_settings()
    credentials = OKXCredentials(
        api_key=resolved.okx_api_key,
        api_secret=resolved.okx_api_secret,
        passphrase=resolved.okx_passphrase,
        flag=resolved.okx_flag,
    )
    return OKXClient.from_credentials(credentials, td_mode=resolved.okx_td_mode)



def make_okx_ws_client(current_settings: Optional[Settings] = None) -> OKXWebSocketClient:
    resolved = current_settings or get_settings()
    return OKXWebSocketClient(
        api_key=resolved.okx_api_key,
        api_secret=resolved.okx_api_secret,
        passphrase=resolved.okx_passphrase,
        url=resolved.okx_ws_url,
    )



def _execution_path(resolved: Settings) -> str:
    return "okx_native" if resolved.use_okx_native else "hummingbot"



def log_pipeline_event(
    event_type: str,
    payload: Dict[str, Any],
    current_settings: Optional[Settings] = None,
) -> None:
    resolved = current_settings or get_settings()
    append_audit_event(
        resolved.audit_log_path,
        {
            "event_type": event_type,
            "execution_path": _execution_path(resolved),
            **payload,
        },
    )



def healthcheck_payload(current_settings: Optional[Settings] = None) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    return {
        "status": "ok",
        "environment": resolved.environment,
        "connector": "okx_native" if resolved.use_okx_native else resolved.okx_connector_id,
        "symbol": resolved.okx_symbol,
        "account_name": resolved.hbot_account_name,
        "execution_enabled": resolved.execution_enabled,
        "paper_mode": resolved.paper_mode,
        "execution_path": _execution_path(resolved),
    }



def risk_check_payload(
    proposal: TradeProposal,
    account: AccountState,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    decision = evaluate_trade(proposal, account, resolved.risk_limits)
    return {
        "approved": decision.approved,
        "reasons": decision.reasons,
        "connector": proposal.connector,
        "symbol": proposal.symbol,
    }



def account_state_payload(
    client: Optional[HummingbotClient] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    active_client = client or make_hbot_client(resolved)
    account_state = sync_account_state(
        client=active_client,
        account_name=resolved.hbot_account_name,
        connector_name=resolved.okx_connector_id,
        trading_pair=resolved.okx_symbol,
    )
    payload = asdict(account_state)
    payload["account_name"] = resolved.hbot_account_name
    payload["connector"] = resolved.okx_connector_id
    payload["symbol"] = resolved.okx_symbol
    payload["execution_path"] = "hummingbot"
    return payload



def okx_account_state_payload(
    client: Optional[OKXClient] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    active_client = client or make_okx_client(resolved)
    account_state = sync_okx_account_state(
        client=active_client,
        inst_id=resolved.okx_symbol,
        ccy="USDT",
        daily_pnl_pct=None,
        symbol_scoped=False,
    )
    payload = asdict(account_state)
    payload["account_name"] = resolved.hbot_account_name
    payload["connector"] = "okx_native"
    payload["symbol"] = resolved.okx_symbol
    payload["execution_path"] = "okx_native"
    return payload



def process_signal_payload(
    signal: StrategySignal,
    account: AccountState,
    client: HummingbotClient,
    connector: str,
    symbol: str,
    account_name: str,
    risk_limits,
    risk_fraction: float,
    execution_enabled: bool,
    paper_mode: bool,
    allowed_symbols: Optional[Any] = None,
) -> Dict[str, Any]:
    proposal = build_trade_proposal(
        signal=signal,
        account=account,
        connector=connector,
        symbol=signal.symbol or symbol,
        risk_limits=risk_limits,
        risk_fraction=risk_fraction,
    )
    decision = evaluate_trade(proposal, account, risk_limits, allowed_symbols=allowed_symbols)
    risk_payload = {
        "approved": decision.approved,
        "reasons": decision.reasons,
        "connector": proposal.connector,
        "symbol": proposal.symbol,
    }
    if not decision.approved:
        execution_payload = {
            "status": "blocked",
            "connector": proposal.connector,
            "symbol": proposal.symbol,
            "reasons": decision.reasons,
        }
    else:
        execution_payload = execute_trade_proposal(
            client=client,
            account_name=account_name,
            proposal=proposal,
            execution_enabled=execution_enabled,
            paper_mode=paper_mode,
            reference_price=signal.entry_price,
        )
    return {
        "signal": asdict(signal),
        "proposal": asdict(proposal),
        "risk": risk_payload,
        "execution": execution_payload,
    }



def emit_signal_audit_events(
    signal: StrategySignal,
    result: Dict[str, Any],
    current_settings: Optional[Settings] = None,
    symbol: Optional[str] = None,
    client_signal_id: Optional[str] = None,
) -> None:
    resolved_symbol = symbol or result.get("proposal", {}).get("symbol")
    base_payload = {
        "symbol": resolved_symbol,
        "side": signal.side,
        "client_signal_id": client_signal_id,
    }
    log_pipeline_event(
        "risk_decision",
        {
            **base_payload,
            "risk_approved": result.get("risk", {}).get("approved"),
            "risk_reasons": result.get("risk", {}).get("reasons"),
        },
        current_settings=current_settings,
    )
    execution = result.get("execution", {})
    if execution.get("status") in {"submitted", "paper", "disabled", "blocked"}:
        log_pipeline_event(
            "order_submitted",
            {
                **base_payload,
                "execution_status": execution.get("status"),
                "order_id": execution.get("order_id"),
                "position_action": result.get("proposal", {}).get("position_action"),
            },
            current_settings=current_settings,
        )
    if execution.get("reconciliation"):
        log_pipeline_event(
            "order_reconciled",
            {
                **base_payload,
                "order_id": execution.get("order_id"),
                "reconciliation_status": execution.get("reconciliation", {}).get("status"),
                "filled_size": execution.get("reconciliation", {}).get("filled_size"),
            },
            current_settings=current_settings,
        )
    log_pipeline_event(
        "signal_processed",
        {
            **base_payload,
            "risk_approved": result.get("risk", {}).get("approved"),
            "execution_status": execution.get("status"),
            "order_id": execution.get("order_id"),
            "reconciliation_status": execution.get("reconciliation", {}).get("status"),
        },
        current_settings=current_settings,
    )



def process_okx_signal_payload(
    signal: StrategySignal,
    account: AccountState,
    client: OKXClient,
    symbol: str,
    risk_limits,
    risk_fraction: float,
    execution_enabled: bool,
    paper_mode: bool,
    allowed_symbols: Optional[Any] = None,
) -> Dict[str, Any]:
    proposal = build_trade_proposal(
        signal=signal,
        account=account,
        connector="okx_native",
        symbol=signal.symbol or symbol,
        risk_limits=risk_limits,
        risk_fraction=risk_fraction,
    )
    decision = evaluate_trade(proposal, account, risk_limits, allowed_symbols=allowed_symbols)
    risk_payload = {
        "approved": decision.approved,
        "reasons": decision.reasons,
        "connector": proposal.connector,
        "symbol": proposal.symbol,
    }
    if not decision.approved:
        execution_payload = {
            "status": "blocked",
            "connector": proposal.connector,
            "symbol": proposal.symbol,
            "reasons": decision.reasons,
        }
    else:
        execution_payload = execute_okx_trade_proposal(
            client=client,
            proposal=proposal,
            execution_enabled=execution_enabled,
            paper_mode=paper_mode,
            reference_price=signal.entry_price,
        )
    return {
        "signal": asdict(signal),
        "proposal": asdict(proposal),
        "risk": risk_payload,
        "execution": execution_payload,
    }



def run_signal_pipeline(
    signal: StrategySignal,
    client: Optional[HummingbotClient] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    active_client = client or make_hbot_client(resolved)
    account = sync_account_state(
        client=active_client,
        account_name=resolved.hbot_account_name,
        connector_name=resolved.okx_connector_id,
        trading_pair=resolved.okx_symbol,
    )
    return process_signal_payload(
        signal=signal,
        account=account,
        client=active_client,
        connector=resolved.okx_connector_id,
        symbol=resolved.okx_symbol,
        account_name=resolved.hbot_account_name,
        risk_limits=_apply_control_state(resolved),
        risk_fraction=resolved.proposal_risk_fraction,
        execution_enabled=resolved.execution_enabled,
        paper_mode=resolved.paper_mode,
        allowed_symbols=resolved.okx_allowed_symbols or None,
    )



def run_okx_native_signal_pipeline(
    signal: StrategySignal,
    client: Optional[OKXClient] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    active_client = client or make_okx_client(resolved)
    account = sync_okx_account_state(
        client=active_client,
        inst_id=resolved.okx_symbol,
        ccy="USDT",
        daily_pnl_pct=None,
        symbol_scoped=False,
    )
    return process_okx_signal_payload(
        signal=signal,
        account=account,
        client=active_client,
        symbol=resolved.okx_symbol,
        risk_limits=_apply_control_state(resolved),
        risk_fraction=resolved.proposal_risk_fraction,
        execution_enabled=resolved.execution_enabled,
        paper_mode=resolved.paper_mode,
        allowed_symbols=resolved.okx_allowed_symbols or None,
    )



def run_primary_signal_pipeline(
    signal: StrategySignal,
    client: Optional[Any] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    if resolved.use_okx_native:
        return run_okx_native_signal_pipeline(signal=signal, client=client, current_settings=resolved)
    return run_signal_pipeline(signal=signal, client=client, current_settings=resolved)



def process_signal_request_payload(
    payload: Dict[str, Any],
    client: Optional[Any] = None,
    current_settings: Optional[Settings] = None,
    auth_header: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_settings = current_settings or get_settings()
    verify_signal_auth(resolved_settings.signal_shared_secret, auth_header)
    client_signal_id = payload.get("client_signal_id", "")
    ensure_signal_not_duplicate(resolved_settings.signal_idempotency_path, client_signal_id)
    signal = StrategySignal(
        side=payload["side"],
        confidence=float(payload["confidence"]),
        entry_price=float(payload["entry_price"]),
        stop_loss_price=float(payload["stop_loss_price"]),
        take_profit_price=float(payload["take_profit_price"]),
        expected_slippage_bps=float(payload["expected_slippage_bps"]),
        leverage=float(payload["leverage"]),
        rationale=payload.get("rationale", ""),
        position_action=payload.get("position_action", "OPEN"),
        pos_side=payload.get("pos_side", ""),
        symbol=payload.get("symbol") or None,
    )
    result = run_primary_signal_pipeline(signal=signal, client=client, current_settings=resolved_settings)
    emit_signal_audit_events(
        signal=signal,
        result=result,
        current_settings=resolved_settings,
        symbol=payload.get("symbol", resolved_settings.okx_symbol),
        client_signal_id=client_signal_id,
    )
    return result



def reconcile_open_orders_payload(
    open_orders: list,
    client: Optional[OKXClient] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    active_client = client or make_okx_client(resolved)
    results = reconcile_open_orders_job(
        client=active_client,
        open_orders=open_orders,
        audit_log_path=resolved.audit_log_path,
        execution_path=_execution_path(resolved),
    )
    return {"results": results, "count": len(results), "poll_interval_seconds": resolved.reconcile_poll_interval_seconds}



def build_ui_summary_payload(
    current_settings: Optional[Settings] = None,
    account_fn: Optional[Any] = None,
    events_limit: int = 100,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    control = read_control_state(resolved.control_state_path)
    events = read_recent_audit_events(resolved.audit_log_path, limit=events_limit)
    counters = summarize_events(events)
    account_payload: Optional[Dict[str, Any]] = None
    account_error: Optional[str] = None
    if account_fn is not None:
        try:
            account_payload = account_fn(resolved)
        except Exception as exc:  # noqa: BLE001
            account_error = f"{type(exc).__name__}: {exc}"
    return {
        "environment": resolved.environment,
        "symbol": resolved.okx_symbol,
        "execution_enabled": resolved.execution_enabled,
        "paper_mode": resolved.paper_mode,
        "okx_flag": resolved.okx_flag,
        "execution_path": _execution_path(resolved),
        "trading_halted": control.trading_halted,
        "halt_reason": control.halt_reason,
        "halted_at": control.halted_at,
        "halted_by": control.halted_by,
        "counters": counters,
        "account": account_payload,
        "account_error": account_error,
        "events": events[-events_limit:],
    }


def ui_halt_action(
    reason: str,
    actor: str,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    state = halt_trading(resolved.control_state_path, reason=reason or "local-ui", actor=actor or "local-ui")
    append_audit_event(
        resolved.audit_log_path,
        {
            "event_type": "admin_action",
            "execution_path": _execution_path(resolved),
            "action": "halt",
            "source": "local_ui",
            "reason": reason,
            "actor": actor,
        },
    )
    return {"trading_halted": state.trading_halted, "halt_reason": state.halt_reason, "halted_by": state.halted_by}


def ui_resume_action(
    actor: str,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    resume_trading(resolved.control_state_path)
    append_audit_event(
        resolved.audit_log_path,
        {
            "event_type": "admin_action",
            "execution_path": _execution_path(resolved),
            "action": "resume",
            "source": "local_ui",
            "actor": actor,
        },
    )
    return {"trading_halted": False}


def run_demo_validation_workflow(
    payload: Dict[str, Any],
    client: Optional[Any] = None,
    current_settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    resolved = current_settings or get_settings()
    demo_settings = Settings(
        environment=resolved.environment,
        okx_connector_id=resolved.okx_connector_id,
        okx_symbol=resolved.okx_symbol,
        okx_api_key=resolved.okx_api_key,
        okx_api_secret=resolved.okx_api_secret,
        okx_passphrase=resolved.okx_passphrase,
        okx_flag="1",
        okx_td_mode=resolved.okx_td_mode,
        okx_ws_url=resolved.okx_ws_url,
        reconcile_poll_interval_seconds=resolved.reconcile_poll_interval_seconds,
        use_okx_native=True,
        hbot_account_name=resolved.hbot_account_name,
        hbot_api_url=resolved.hbot_api_url,
        hbot_api_username=resolved.hbot_api_username,
        hbot_api_password=resolved.hbot_api_password,
        execution_enabled=True,
        paper_mode=False,
        proposal_risk_fraction=resolved.proposal_risk_fraction,
        audit_log_path=resolved.audit_log_path,
        signal_shared_secret=resolved.signal_shared_secret,
        signal_idempotency_path=resolved.signal_idempotency_path,
        control_state_path=resolved.control_state_path,
        admin_shared_secret=resolved.admin_shared_secret,
        admin_nonce_path=resolved.admin_nonce_path,
        admin_small_trade_usd=resolved.admin_small_trade_usd,
        admin_large_trade_usd=resolved.admin_large_trade_usd,
        risk_limits=resolved.risk_limits,
    )
    auth_header = demo_settings.signal_shared_secret if demo_settings.signal_shared_secret else None
    return process_signal_request_payload(payload, client=client, current_settings=demo_settings, auth_header=auth_header)


UI_HTML = """<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>agent_trader dashboard</title>
<style>
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;padding:16px;background:#0b0d10;color:#e6e7ea}
h1{font-size:18px;margin:0 0 12px}
.card{background:#14181d;border:1px solid #232a33;border-radius:8px;padding:12px;margin-bottom:12px}
.row{display:flex;gap:12px;flex-wrap:wrap}
.row > .card{flex:1 1 320px}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:13px}
.kv div:nth-child(odd){color:#8b95a2}
button{background:#2a333d;color:#e6e7ea;border:1px solid #39434f;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px}
button.halt{background:#4a1a1a;border-color:#6e2929}
button.resume{background:#1a3a1f;border-color:#2a5a33}
button:disabled{opacity:0.5;cursor:not-allowed}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:6px 8px;text-align:left;border-bottom:1px solid #232a33;vertical-align:top}
th{color:#8b95a2;font-weight:500}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px}
.badge.ok{background:#1a3a1f;color:#7ddc8b}
.badge.danger{background:#4a1a1a;color:#ff9292}
.badge.admin{background:#2d2a4a;color:#b7adff}
.badge.info{background:#1e2a3a;color:#7dacff}
.status-halted{color:#ff9292;font-weight:600}
.status-live{color:#7ddc8b;font-weight:600}
pre{margin:0;white-space:pre-wrap;word-break:break-word;font-size:11px;color:#8b95a2}
</style>
</head>
<body>
<h1>agent_trader — local dashboard</h1>
<div class=\"row\">
  <div class=\"card\" style=\"flex:0 0 320px\">
    <div id=\"status-line\"></div>
    <div style=\"margin-top:10px\">
      <button id=\"halt-btn\" class=\"halt\">HALT</button>
      <button id=\"resume-btn\" class=\"resume\" style=\"display:none\">RESUME</button>
    </div>
    <div class=\"kv\" style=\"margin-top:12px\" id=\"meta-kv\"></div>
  </div>
  <div class=\"card\">
    <h3 style=\"margin-top:0\">账户</h3>
    <div class=\"kv\" id=\"account-kv\"></div>
    <pre id=\"account-error\"></pre>
  </div>
  <div class=\"card\">
    <h3 style=\"margin-top:0\">计数器（最近 100 条事件）</h3>
    <div class=\"kv\" id=\"counter-kv\"></div>
  </div>
</div>
<div class=\"card\">
  <h3 style=\"margin-top:0\">按合约敞口</h3>
  <table>
    <thead><tr><th>合约</th><th>名义金额 (USD)</th></tr></thead>
    <tbody id=\"positions-body\"><tr><td colspan=\"2\" style=\"color:#8b95a2\">暂无持仓</td></tr></tbody>
  </table>
</div>
<div class=\"card\">
  <h3 style=\"margin-top:0\">审计事件</h3>
  <table>
    <thead><tr><th>time</th><th>kind</th><th>event</th><th>symbol</th><th>detail</th></tr></thead>
    <tbody id=\"events-body\"></tbody>
  </table>
</div>
<script>
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});if(!r.ok){const t=await r.text();throw new Error(t||r.statusText)}return r.json()}
async function getJson(path){const r=await fetch(path);if(!r.ok)throw new Error(r.statusText);return r.json()}
function kv(el,map){el.innerHTML='';for(const k of Object.keys(map)){const a=document.createElement('div');a.textContent=k;const b=document.createElement('div');b.textContent=map[k]??'';el.appendChild(a);el.appendChild(b)}}
function classify(e){const t=e.event_type||'';if(t==='admin_action')return'admin';if(t==='risk_decision')return e.risk_approved===false?'danger':'ok';if(t==='order_submitted')return e.execution_status==='blocked'?'danger':(e.execution_status==='submitted'?'ok':'info');if(t==='order_reconciled')return e.reconciliation_status==='filled'?'ok':'info';return'info'}
async function refresh(){try{const s=await getJson('/ui/summary');const sl=document.getElementById('status-line');if(s.trading_halted){sl.innerHTML='<span class=\"status-halted\">HALTED</span> — '+(s.halt_reason||'')+' by '+(s.halted_by||'');document.getElementById('halt-btn').style.display='none';document.getElementById('resume-btn').style.display='inline-block'}else{sl.innerHTML='<span class=\"status-live\">LIVE</span>';document.getElementById('halt-btn').style.display='inline-block';document.getElementById('resume-btn').style.display='none'}kv(document.getElementById('meta-kv'),{environment:s.environment,symbol:s.symbol,path:s.execution_path,execution_enabled:s.execution_enabled,paper_mode:s.paper_mode,okx_flag:s.okx_flag});kv(document.getElementById('counter-kv'),s.counters||{});if(s.account){kv(document.getElementById('account-kv'),{equity_usd:s.account.equity_usd,avail_equity_usd:s.account.available_equity_usd??'—',margin_ratio:s.account.margin_ratio??'—',used_margin_usd:s.account.used_margin_usd??'—',daily_pnl_pct:s.account.daily_pnl_pct,exposure_usd:s.account.current_exposure_usd,open_positions:s.account.open_positions,connector:s.account.connector,symbol:s.account.symbol});const pb=document.getElementById('positions-body');pb.innerHTML='';const bySym=s.account.positions_by_symbol||{};const entries=Object.entries(bySym).sort((a,b)=>b[1]-a[1]);if(entries.length===0){pb.innerHTML='<tr><td colspan=\"2\" style=\"color:#8b95a2\">暂无持仓</td></tr>'}else{entries.forEach(([sym,val])=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${sym}</td><td>${Number(val).toFixed(2)}</td>`;pb.appendChild(tr)})}}else{document.getElementById('account-kv').innerHTML='';document.getElementById('positions-body').innerHTML='<tr><td colspan=\"2\" style=\"color:#8b95a2\">暂无持仓</td></tr>'}document.getElementById('account-error').textContent=s.account_error||'';const body=document.getElementById('events-body');body.innerHTML='';(s.events||[]).slice().reverse().forEach(e=>{const tr=document.createElement('tr');const cls=classify(e);const ts=(e.timestamp||'').replace('T',' ').slice(0,19);const detail=e.reasons?e.reasons.join(', '):(e.reason||e.action||e.execution_status||e.reconciliation_status||'');tr.innerHTML=`<td>${ts}</td><td><span class=\"badge ${cls}\">${cls}</span></td><td>${e.event_type||''}</td><td>${e.symbol||''}</td><td>${detail}</td>`;body.appendChild(tr)})}catch(e){console.error(e)}}
document.getElementById('halt-btn').addEventListener('click',async()=>{const reason=prompt('halt reason?','manual');if(reason===null)return;try{await post('/ui/halt',{reason,actor:'local-ui'});refresh()}catch(e){alert('halt failed: '+e.message)}})
document.getElementById('resume-btn').addEventListener('click',async()=>{if(!confirm('Resume trading?'))return;try{await post('/ui/resume',{actor:'local-ui'});refresh()}catch(e){alert('resume failed: '+e.message)}})
refresh();setInterval(refresh,3000)
</script>
</body>
</html>"""


def _is_local_request(request) -> bool:
    host = getattr(getattr(request, "client", None), "host", None)
    return host in {"127.0.0.1", "::1", "localhost"}


try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import HTMLResponse

    from agent_trader import admin_api

    app = FastAPI(title="OKX Native + Hummingbot AI Agent MVP")

    def _admin_pipeline_runner(signal: StrategySignal, current_settings: Settings) -> Dict[str, Any]:
        return run_primary_signal_pipeline(signal=signal, current_settings=current_settings)

    def _admin_headers(timestamp: Optional[str], nonce: Optional[str], signature: Optional[str]) -> tuple:
        if not timestamp or not nonce or not signature:
            raise HTTPException(status_code=401, detail="missing admin auth headers")
        return timestamp, nonce, signature

    def _admin_errors(exc: Exception) -> HTTPException:
        if isinstance(exc, admin_api.AdminAuthError):
            return HTTPException(status_code=401, detail=str(exc))
        if isinstance(exc, admin_api.AdminReplayError):
            return HTTPException(status_code=409, detail=str(exc))
        if isinstance(exc, admin_api.AdminTierViolation):
            return HTTPException(status_code=400, detail=str(exc))
        return HTTPException(status_code=500, detail=str(exc))

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        return healthcheck_payload()

    @app.get("/account-state")
    def account_state() -> Dict[str, Any]:
        resolved = get_settings()
        if resolved.use_okx_native:
            return okx_account_state_payload(current_settings=resolved)
        return account_state_payload(current_settings=resolved)

    @app.post("/signal")
    def submit_signal(payload: Dict[str, Any], x_signal_secret: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        return process_signal_request_payload(payload, current_settings=get_settings(), auth_header=x_signal_secret)

    @app.get("/admin/status")
    def admin_status(
        x_admin_timestamp: Optional[str] = Header(default=None),
        x_admin_nonce: Optional[str] = Header(default=None),
        x_admin_signature: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        ts, nonce, sig = _admin_headers(x_admin_timestamp, x_admin_nonce, x_admin_signature)
        try:
            return admin_api.handle_status(get_settings(), ts, nonce, sig)
        except Exception as exc:
            raise _admin_errors(exc) from exc

    @app.post("/admin/halt")
    def admin_halt(
        payload: Dict[str, Any],
        x_admin_timestamp: Optional[str] = Header(default=None),
        x_admin_nonce: Optional[str] = Header(default=None),
        x_admin_signature: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        ts, nonce, sig = _admin_headers(x_admin_timestamp, x_admin_nonce, x_admin_signature)
        try:
            return admin_api.handle_halt(get_settings(), payload, ts, nonce, sig)
        except Exception as exc:
            raise _admin_errors(exc) from exc

    @app.post("/admin/resume")
    def admin_resume(
        payload: Dict[str, Any],
        x_admin_timestamp: Optional[str] = Header(default=None),
        x_admin_nonce: Optional[str] = Header(default=None),
        x_admin_signature: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        ts, nonce, sig = _admin_headers(x_admin_timestamp, x_admin_nonce, x_admin_signature)
        try:
            return admin_api.handle_resume(get_settings(), payload, ts, nonce, sig)
        except Exception as exc:
            raise _admin_errors(exc) from exc

    def _ui_account_fn(resolved: Settings) -> Dict[str, Any]:
        if resolved.use_okx_native:
            return okx_account_state_payload(current_settings=resolved)
        return account_state_payload(current_settings=resolved)

    @app.get("/ui/", response_class=HTMLResponse)
    def ui_index(request: Request) -> HTMLResponse:
        if not _is_local_request(request):
            raise HTTPException(status_code=403, detail="local only")
        return HTMLResponse(content=UI_HTML)

    @app.get("/ui/summary")
    def ui_summary(request: Request) -> Dict[str, Any]:
        if not _is_local_request(request):
            raise HTTPException(status_code=403, detail="local only")
        return build_ui_summary_payload(current_settings=get_settings(), account_fn=_ui_account_fn)

    @app.get("/ui/events")
    def ui_events(request: Request, limit: int = 100) -> Dict[str, Any]:
        if not _is_local_request(request):
            raise HTTPException(status_code=403, detail="local only")
        resolved = get_settings()
        events = read_recent_audit_events(resolved.audit_log_path, limit=limit)
        return {"events": events, "count": len(events)}

    @app.post("/ui/halt")
    def ui_halt(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
        if not _is_local_request(request):
            raise HTTPException(status_code=403, detail="local only")
        reason = str(payload.get("reason", "local-ui"))
        actor = str(payload.get("actor", "local-ui"))
        return ui_halt_action(reason=reason, actor=actor, current_settings=get_settings())

    @app.post("/ui/resume")
    def ui_resume(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
        if not _is_local_request(request):
            raise HTTPException(status_code=403, detail="local only")
        actor = str(payload.get("actor", "local-ui"))
        return ui_resume_action(actor=actor, current_settings=get_settings())

    @app.post("/admin/manual_trade")
    def admin_manual_trade(
        payload: Dict[str, Any],
        x_admin_timestamp: Optional[str] = Header(default=None),
        x_admin_nonce: Optional[str] = Header(default=None),
        x_admin_signature: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        ts, nonce, sig = _admin_headers(x_admin_timestamp, x_admin_nonce, x_admin_signature)
        try:
            return admin_api.handle_manual_trade(
                get_settings(),
                payload,
                ts,
                nonce,
                sig,
                pipeline_runner=_admin_pipeline_runner,
            )
        except Exception as exc:
            raise _admin_errors(exc) from exc

except ImportError:  # pragma: no cover
    app = None
