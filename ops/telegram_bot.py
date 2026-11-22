"""AEGIS Interactive Two-Way Telegram Control Bot.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations:
- AEGIS Project Review Report (Section 6.3: Mobile Command & Control Protocol)
"""

import os
import uuid

from src.connector.server import AegisConnectorServer
from src.gate.kill_switch import StandaloneKillSwitch


class TelegramCommandHandler:
    """Two-way Telegram Bot command controller for supervisor oversight and emergency response.
    
    Guarantees Section 6 Product enhancement:
    - Provides real-time owner control (status, approve, pause, kill) via authenticated chat channel.
    """

    def __init__(
        self,
        server: AegisConnectorServer,
        authorized_chat_id: str | None = None,
        authorized_user_id: str | None = None,
        kill_switch: StandaloneKillSwitch | None = None
    ) -> None:
        self.server = server
        self.authorized_chat_id = (
            authorized_chat_id
            or os.environ.get("AEGIS_TELEGRAM_CHAT_ID", "")
            or os.environ.get("TELEGRAM_CHAT_ID", "")
        )
        self.authorized_user_id = (
            authorized_user_id
            or os.environ.get("AEGIS_TELEGRAM_USER_ID", "")
            or os.environ.get("TELEGRAM_USER_ID", "")
        )
        self.kill_switch = kill_switch or StandaloneKillSwitch()

    def handle_command(self, user_chat_id: str, command_text: str, sender_user_id: str | None = None) -> str:
        """Process an incoming command from Telegram, verifying authorization first."""
        # 1. Authorization check (Fail closed: must have authorized_chat_id configured - B4 & Proof 8)
        if not self.authorized_chat_id or str(user_chat_id).strip() != str(self.authorized_chat_id).strip():
            return "⛔ Unauthorized: Access denied. Telegram command interface requires valid AEGIS_TELEGRAM_CHAT_ID authorization."

        # 2. Sender user ID verification if configured
        if self.authorized_user_id and sender_user_id and str(sender_user_id).strip() != str(self.authorized_user_id).strip():
            return "⛔ Unauthorized: Sender user ID does not match AEGIS_TELEGRAM_USER_ID."

        text = command_text.strip()
        parts = text.split()
        cmd = parts[0].lower() if parts else ""

        if cmd == "/status":
            return self._handle_status()
        elif cmd == "/positions":
            return self._handle_positions()
        elif cmd in ("/kill", "/emergency"):
            reason = " ".join(parts[1:]) if len(parts) > 1 else "Emergency Kill Switch triggered via Telegram"
            return self._handle_kill(reason)
        elif cmd == "/pause":
            return self._handle_pause()
        elif cmd == "/approve":
            if len(parts) < 2:
                return "⚠️ Usage: `/approve <proposal_id>`"
            return self._handle_approve(parts[1])
        elif cmd in ("/help", "/start"):
            return (
                "🛡️ *AEGIS Two-Way Command Center*\n"
                "- `/status`: View live equity, cash, and gate limits\n"
                "- `/positions`: List active portfolio positions\n"
                "- `/approve <id>`: Sign and execute a pending draft order\n"
                "- `/pause`: Temporarily engage safety pause\n"
                "- `/kill <reason>`: Engage Emergency Kill Switch & cancel open orders"
            )
        else:
            return f"❓ Unknown command '{cmd}'. Type `/help` for available operations."

    def _handle_status(self) -> str:
        acc = self.server.get_account()
        run_state = self.server.get_run_state()
        ks_engaged = self.kill_switch.is_engaged() or self.server.kill_switch_active
        mode = run_state.get("mode", self.server.mode)
        equity = acc.get("equity", "0.00")
        cash = acc.get("cash", "0.00")
        positions_count = len(acc.get("positions", {}))

        status_icon = "🔴 STOPPED" if ks_engaged else "🟢 RUNNING"

        return (
            f"📊 *AEGIS SYSTEM STATUS*\n"
            f"- State: {status_icon}\n"
            f"- Mode: `{mode}`\n"
            f"- Equity: `${equity}` USDT\n"
            f"- Cash: `${cash}` USDT\n"
            f"- Open Positions: {positions_count}\n"
            f"- Daily Loss: `${run_state.get('daily_realized_loss', '0.00')}`\n"
            f"- Kill Switch: {'ENGAGED' if ks_engaged else 'DISENGAGED'}"
        )

    def _handle_positions(self) -> str:
        acc = self.server.get_account()
        positions = acc.get("positions", {})
        if not positions:
            return "💼 *Positions*: No active positions held."

        lines = ["💼 *ACTIVE PORTFOLIO POSITIONS*"]
        for sym, pos in positions.items():
            lines.append(
                f"- `{sym}`: Size={pos['size']} | Entry=${pos.get('avg_price', '0.00')} | Notional=${pos.get('notional', '0.00')}"
            )
        return "\n".join(lines)

    def _handle_kill(self, reason: str) -> str:
        self.kill_switch.engage(reason=reason, operator="Telegram Supervisor")
        self.server.kill_switch_active = True
        self.server.broker.cancel_all_open_orders()
        return f"🚨 *EMERGENCY KILL SWITCH ENGAGED*\nReason: {reason}\nAll open orders have been canceled."

    def _handle_pause(self) -> str:
        self.kill_switch.engage(reason="Safety pause via chat", operator="Telegram Supervisor")
        self.server.kill_switch_active = True
        return "⏸️ *AEGIS PAUSED*: Safety pause active. Orders halted."

    def _handle_approve(self, proposal_id_str: str) -> str:
        try:
            p_id = uuid.UUID(proposal_id_str.strip())
        except ValueError:
            return f"❌ Invalid UUID format: `{proposal_id_str}`"

        owner_secret = (
            os.environ.get("AEGIS_APPROVAL_SECRET")
            or os.environ.get("AEGIS_OWNER_SECRET")
            or os.environ.get("AEGIS_OWNER_TOKEN")
        )
        if not owner_secret:
            return "❌ *APPROVAL REJECTED*: AEGIS_APPROVAL_SECRET is not configured on this server."

        stored = self.server.proposals.get(p_id)
        if not stored:
            return f"❌ Proposal ID `{p_id}` not found in database."

        from datetime import UTC, datetime, timedelta

        from src.gate.evaluator import create_order_approval_signature
        now = datetime.now(UTC)
        expires_at = (now + timedelta(hours=1)).isoformat()
        nonce = uuid.uuid4().hex

        prop = stored.proposal
        sig = create_order_approval_signature(
            secret=owner_secret,
            symbol=prop.symbol,
            side=prop.side.value,
            order_type=prop.order_type.value,
            size=prop.size,
            price=prop.price,
            stop_loss=prop.stop_loss,
            take_profit=prop.take_profit,
            expires_at=expires_at,
            nonce=nonce
        )

        res = self.server.approve_and_place_order(
            proposal_id=p_id,
            approval_signature=sig,
            approval_expires_at=expires_at,
            approval_nonce=nonce,
            current_ts=now
        )
        if res.get("passed"):
            order_data = res.get("order", {})
            return f"✅ *PROPOSAL APPROVED & FILLED*\nOrder ID: `{order_data.get('order_id')}`\nStatus: {order_data.get('status')}"
        else:
            reasons = "; ".join(res.get("reasons", ["Rejected by Risk Gate"]))
            return f"❌ *APPROVAL REJECTED BY RISK GATE*\n{reasons}"

    def poll_updates(self, bot_token: str | None = None, offset: int | None = None) -> int:
        """Fetch pending Telegram messages, dispatch commands, and persist update offset."""
        import json
        import urllib.request
        from pathlib import Path

        offset_file = Path("data/telegram_offset.txt")
        current_offset = offset
        if current_offset is None:
            if offset_file.exists():
                try:
                    current_offset = int(offset_file.read_text(encoding="utf-8").strip())
                except ValueError:
                    current_offset = 0
            else:
                current_offset = 0

        token = bot_token or os.environ.get("AEGIS_TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return current_offset
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset={current_offset}&timeout=5"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AEGIS-TelegramBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("result", []):
                    update_id = item.get("update_id", current_offset)
                    current_offset = max(current_offset, update_id + 1)
                    msg = item.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    sender_id = str(msg.get("from", {}).get("id", ""))
                    text = msg.get("text", "")
                    if text:
                        reply = self.handle_command(user_chat_id=chat_id, command_text=text, sender_user_id=sender_id)
                        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                        send_payload = json.dumps({"chat_id": chat_id, "text": reply}).encode("utf-8")
                        send_req = urllib.request.Request(send_url, data=send_payload, headers={"Content-Type": "application/json"})
                        urllib.request.urlopen(send_req, timeout=5)
            # Persist offset
            offset_file.parent.mkdir(parents=True, exist_ok=True)
            offset_file.write_text(str(current_offset), encoding="utf-8")
        except Exception:  # noqa: BLE001, S110
            pass
        return current_offset
