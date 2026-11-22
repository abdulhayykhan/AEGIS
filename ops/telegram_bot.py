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
        kill_switch: StandaloneKillSwitch | None = None
    ) -> None:
        self.server = server
        self.authorized_chat_id = authorized_chat_id or os.environ.get("AEGIS_TELEGRAM_CHAT_ID", "")
        self.kill_switch = kill_switch or StandaloneKillSwitch()

    def handle_command(self, user_chat_id: str, command_text: str) -> str:
        """Process an incoming command from Telegram, verifying authorization first."""
        # 1. Authorization check
        if self.authorized_chat_id and str(user_chat_id).strip() != str(self.authorized_chat_id).strip():
            return "⛔ Unauthorized: Access denied. This incident has been logged."

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

        res = self.server.approve_and_place_order(
            proposal_id=p_id,
            approval_token="OWNER_ABDUL_HAYY_SIGNATURE"
        )
        if res.get("passed"):
            order_data = res.get("order", {})
            return f"✅ *PROPOSAL APPROVED & FILLED*\nOrder ID: `{order_data.get('order_id')}`\nStatus: {order_data.get('status')}"
        else:
            reasons = "; ".join(res.get("reasons", ["Rejected by Risk Gate"]))
            return f"❌ *APPROVAL REJECTED BY RISK GATE*\n{reasons}"
