#!/usr/bin/env python3
"""
Social-Deduction Engine v3
--------------------------
変更点
* bid と talk を 1 回の呼び出しで同時に返す
* 会話履歴のみを mem_log に保管
* 公開メタから status / winner を削除
* DM の内容もログとして表示、保存
* Agent と GameMaster を分離
"""

from __future__ import annotations
import argparse, importlib, json, random, sys
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage
from langchain.output_parsers.json import SimpleJsonOutputParser


# ---------- エージェント ----------
class Agent:
    def __init__(self, name: str, role: str | None,
                 sys_prompt: str, llm: ChatOpenAI):
        self.name, self.role = name, role
        self.llm = llm
        self.mem_log: List[Tuple[int, str, str, str]] = []   # (turn, sender, recipients, text)

    def decide(self, turn: int, meta_pub, public_log) -> dict:
        # Create history string from mem_log
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                           for turn, sender, recv, txt in self.mem_log[-30:])
        
        js = self.main_chain.invoke({
            "meta": json.dumps(meta_pub, ensure_ascii=False),
            "history": history
        })
        return js

class Player(Agent):
    def __init__(self, name: str, role: str | None,
                 sys_prompt: str, llm: ChatOpenAI):
        super().__init__(name, role, sys_prompt, llm)
        parser = SimpleJsonOutputParser()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human",
             "=== PUBLIC META ===\n{meta}\n"
             "=== RECENT CONVERSATIONS ===\n{history}\n"
             "Message history format is <turn>: <sender>▶<recipient>: <message>\n"
             "Bid to speak (0-1) and *optionally* send a message.\n"
             "Important mechanics:\n"
             "- All players and GM bid simultaneously in each turn\n"
             "- Only the highest bidder's message will be used\n"
             "- The conversation follows a strict pattern: bid → speak → bid → speak ...\n"
             "- This applies to both public messages and DMs\n"
             "- Even if you want to send a DM, you must win the bid first\n\n"
             "Bidding guidelines:\n"
             "Higher bids indicate stronger desire to speak.\n"
             "Consider your role, the current phase, and game state when bidding.\n"
             "Use 1.0 bids sparingly - only when you believe you have critical information or a strong strategic reason to speak.\n"
             "Lower bids (0.3-0.7) are appropriate for general discussion or when others should speak first.\n"
             "Use 0.0 bids when you don't want to speak or you finished your voting or ability.\n"
             "When sending messages:\n"
             "- Use \"to\": \"ALL\" for public messages visible to everyone\n"
             "- Use \"to\": \"GM\" for private messages only visible to the GM (use this for voting or your ability)\n"
             "- Use \"to\": \"P1,P2,...\" to send DMs to specific players\n"
             "Remember that DMs are only visible to the specified recipients.\n"
             "Respond ONLY JSON:\n"
             "{{\"bid\": <0.0-1.0 (float)>, \"reason\": <free text>, \"msg\": <string>, \"to\": \"ALL\"|\"GM\"|\"P1,P2,...\"}}"),
        ])
        self.main_chain = prompt | llm | parser


class GameMaster(Player):
    def __init__(self, name: str, sys_prompt: str, llm: ChatOpenAI):
        super().__init__(name, None, sys_prompt, llm)
        parser = SimpleJsonOutputParser()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human",
             "=== PUBLIC META ===\n{meta}\n"
             "=== RECENT CONVERSATIONS ===\n{history}\n"
             "Message history format is <turn>: <sender>▶<recipient>: <message>\n"
             "Bid to speak (0-1) and *optionally* send a message.\n"
             "Important mechanics:\n"
             "- All players and GM bid simultaneously in each turn\n"
             "- Only the highest bidder's message will be used\n"
             "- The conversation follows a strict pattern: bid → speak → bid → speak ...\n"
             "- This applies to both public messages and DMs\n"
             "- Even if you want to send a DM, you must win the bid first\n\n"
             "- PUBLIC META is automatically updated based on the conversation, if it is necessary\n" 
             "Bidding guidelines:\n"
             "Higher bids indicate stronger desire to speak.\n"
             "Consider the current phase and game state when bidding.\n"
             "Use 1.0 bids only when:\n"
             "- Announcing phase changes (e.g., starting vote phase, night phase)\n"
             "- Enforcing rules or correcting player behavior\n"
             "Use lower bids (0.3-0.7) for general game management and responses.\n"
             "Use 0.0 bids when you don't need to talk or you are waiting players' DMs.\n"
             "When sending messages:\n"
             "- Use \"to\": \"ALL\" for public messages visible to everyone\n"
             "- Use \"to\": \"P1,P2,...\" to send DMs to specific players\n"
             "Remember that DMs are only visible to the specified recipients.\n"
             "Respond ONLY JSON:\n"
             "{{\"bid\": <0.0-1.0 (float)>, \"msg\": <string>, "
             "\"to\": \"ALL\"|\"P1,P2,...\", \"reason\": <free text>}}"),
        ])
        self.main_chain = prompt | llm | parser

        # GM用のメタ更新チェーン
        self.meta_chain = ChatPromptTemplate.from_messages([
            ("system",
             "You are the hidden reasoning engine for the GM.\n"
             "Given the latest public message and current meta, "
             "decide whether the public meta needs to change.\n" 
             "Return ONLY valid JSON:\n"
             "{{\"update_pub\": {{...}}, \"update_priv\": {{...}}, "
             "\"reason\": <why change or '' if none>}}"),
            ("human",
             "LATEST PUBLIC MESSAGE:\n{last_msg}\n"
             "META_PUB:\n{meta_pub}\nMETA_PRIV:\n{meta_priv}")
        ]) | llm | parser

    def get_meta_updates(self, speaker: str, msg: str,
                     meta_pub: Dict, meta_priv: Dict,
                     pub_log) -> dict:
        """
        GM の LLM 思考でメタを編集する。
        返り値: dict {"update_pub": {...}, "update_priv": {...}, "reason": "..."}
        """
        return self.meta_chain.invoke({
            "last_msg": f"{speaker}: {msg}",
            "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
            "meta_priv": json.dumps(meta_priv, ensure_ascii=False)
        })

# ---------- メインループ ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--players", type=int, default=5)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", default="game_log.json")
    args = ap.parse_args()

    rules = importlib.import_module(args.rules)
    names = [f"P{i+1}" for i in range(args.players)]

    meta_pub = rules.init_meta_pub(names)     # phase / alive / dead など
    meta_priv = rules.init_meta_priv(names)   # 役職など

    llm = ChatOpenAI(model_name=args.model)
    agents: Dict[str, Player] = {}

    # プレイヤー
    for n in names:
        role = rules.assign_role(n, meta_priv)
        agents[n] = Player(n, role,
                          rules.player_sys_prompt(n, role, args.lang),
                          llm)
    # GM
    agents["GM"] = GameMaster("GM",
                             rules.gm_sys_prompt(args.lang), llm)

    # ログ
    public_log: List[Tuple[int, str]] = []  # [(turn, text)]
    dm_log: List[Tuple[int, str, str, str]] = []  # [(turn, sender, receiver, text)]
    full_json_log = []
    turn = 0
    winner: str | None = None
    
    # JSONログファイルが存在するか確認し、存在しなければ空の配列で初期化
    log_path = Path(args.out)
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                full_json_log = json.load(f)
        except json.JSONDecodeError:
            # ファイルが壊れている場合は新規作成
            full_json_log = []
    
    # JSONログを追記する関数
    def append_to_log(entry):
        full_json_log.append(entry)
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(full_json_log, ensure_ascii=False, indent=2, fp=f)

    while winner is None:
        turn += 1
        # ❶ 各エージェントが bid+msg を同時提出
        bids, pkgs = {}, {}
        for a in agents.values():
            pkgs[a.name] = pkg = a.decide(turn, meta_pub, public_log)
            bids[a.name] = float(pkg["bid"])
            
            # 全エージェントの出力をログに追加
            log_entry = {
                "turn": turn,
                "phase": "bid",
                "agent": a.name,
                "bid": float(pkg["bid"]),
                "msg": pkg["msg"].strip(),
                "to": pkg["to"],
                "reason": pkg.get("reason", "")
            }
            append_to_log(log_entry)

        # ❷ 最高 bid のメッセージを採用
        max_bid = max(bids.values())
        speaker = random.choice([n for n, b in bids.items() if b == max_bid])
        pkg = pkgs[speaker]
        utter = pkg["msg"].strip()
        
        # Convert to "ALL" if all players are recipients
        recipients = [x.strip() for x in pkg["to"].split(",")]
        if all(name in recipients for name in names):
            recipients = ["ALL"]

        # 選択結果をログに記録
        append_to_log({
            "turn": turn,
            "phase": "selection",
            "selected_speaker": speaker,
            "max_bid": max_bid
        })

        if utter:
            # 公開ログ更新
            if "ALL" in recipients:
                public_log.append((turn, f"{speaker}: {utter}"))
                print(f"[{turn:02}] {speaker}▶ALL: {utter}")
            else:
                # DMの場合
                for recipient in recipients:
                    dm_log.append((turn, speaker, recipient, utter))
                recipients_str = ",".join(recipients)
                print(f"[{turn:02}] {speaker}▶DM({recipients_str}): {utter}")
            
            # 各エージェントの private memory に追加
            if "ALL" in recipients:
                for agent in agents.values():
                    agent.mem_log.append((turn, speaker, "ALL", utter))
            else:
                # 発言者のログに記録
                agents[speaker].mem_log.append((turn, speaker, ",".join(recipients), utter))
                # 受信者のログに記録
                for r in recipients:
                    agents[r].mem_log.append((turn, speaker, r, utter))
            
            # メッセージ実行をログに記録
            append_to_log({
                "turn": turn, 
                "phase": "message",
                "speaker": speaker,
                "to": recipients, 
                "is_dm": "ALL" not in recipients,
                "msg": utter
            })

        # ❸ GM のメタ更新（LLM reasoning）
        meta_updates = agents["GM"].get_meta_updates(
            speaker, utter,
            meta_pub, meta_priv,
            public_log)

        # GM更新をログに記録
        append_to_log({
            "turn": turn,
            "phase": "meta_update",
            "update_pub": meta_updates.get("update_pub", {}),
            "reason": meta_updates.get("reason", "")
        })

        # 返って来た dict でメタを書き換え
        meta_pub.update(meta_updates.get("update_pub", {}))
        meta_priv.update(meta_updates.get("update_priv", {}))

        # ❹ 終了判定
        winner = rules.check_end(meta_pub, meta_priv)

    print(f"*** Game End. Winner = {winner} ***")
    
    # ゲーム終了をログに記録
    append_to_log({"phase": "end", "winner": winner})
    print("log →", args.out)

if __name__ == "__main__":
    sys.exit(main())
