#!/usr/bin/env python3
"""
Game Logging Module
------------------
Modularized logging system for social deduction games.
Provides clean interfaces for logging different types of game events.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class LogEvent:
    """Base class for all log events"""
    turn: int
    event_type: str
    data: Dict[str, Any]


@dataclass
class SetupEvent(LogEvent):
    """Game setup event"""
    def __init__(self, roles: Dict[str, str], initial_meta: Dict[str, Any]):
        super().__init__(
            turn=0,
            event_type="setup",
            data={
                "roles": roles,
                "initial_meta": initial_meta
            }
        )


@dataclass
class BidEvent(LogEvent):
    """Player bidding event"""
    def __init__(self, turn: int, agent: str, bid: float, msg: str, to: str, reason: str):
        super().__init__(
            turn=turn,
            event_type="bid",
            data={
                "agent": agent,
                "bid": bid,
                "msg": msg.strip(),
                "to": to,
                "reason": reason
            }
        )


@dataclass
class MessageEvent(LogEvent):
    """Message execution event"""
    def __init__(self, turn: int, speaker: str, recipients: List[str], message: str, 
                 is_dm: bool, selection_reason: str = ""):
        super().__init__(
            turn=turn,
            event_type="message",
            data={
                "speaker": speaker,
                "recipients": recipients,
                "message": message.strip(),
                "is_dm": is_dm,
                "selection_reason": selection_reason
            }
        )


@dataclass
class SystemDecisionEvent(LogEvent):
    """System decision event"""
    def __init__(self, turn: int, system_response: Dict[str, Any]):
        super().__init__(
            turn=turn,
            event_type="system_decision",
            data={"system_response": system_response}
        )


@dataclass
class MetaUpdateEvent(LogEvent):
    """Meta information update event"""
    def __init__(self, turn: int, public_changes: Dict[str, Any], private_changes: Dict[str, Any]):
        super().__init__(
            turn=turn,
            event_type="meta_update",
            data={
                "public_changes": public_changes,
                "private_changes": private_changes
            }
        )


@dataclass
class GameEndEvent(LogEvent):
    """Game end event"""
    def __init__(self, winner: Optional[str], total_turns: int, completed: bool):
        super().__init__(
            turn=total_turns,
            event_type="game_end",
            data={
                "winner": winner,
                "total_turns": total_turns,
                "completed": completed
            }
        )


class GameEventLogger:
    """
    Main game event logger that handles all logging operations.
    Provides clean interfaces for logging different types of events.
    """
    
    def __init__(self, out_dir: str):
        """Initialize the game event logger"""
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize log files
        self._setup_log_files()
        
        # Track meta states for change detection
        self.prev_pub_meta = {}
        self.prev_priv_meta = {}
    
    def _setup_log_files(self):
        """Setup log files for writing"""
        # Detailed JSON log
        self.detailed_file = open(self.out_dir / "game_log.json", 'w', encoding='utf-8')
        self.detailed_file.write("[\n")
        self.first_detailed_entry = True
        
        # Human-readable summary log
        self.summary_file = open(self.out_dir / "game_summary.txt", 'w', encoding='utf-8')
        self.summary_file.write("=== SOCIAL DEDUCTION GAME LOG ===\n\n")
        self.summary_file.flush()
    
    def log_event(self, event: LogEvent, console_output: bool = True):
        """
        Log a game event to both detailed and summary logs.
        
        Args:
            event: The LogEvent to log
            console_output: Whether to print to console (default: True)
        """
        # Log to detailed JSON file
        self._log_detailed(event)
        
        # Log to summary file and console based on event type
        if event.event_type == "setup":
            self._log_setup(event, console_output)
        elif event.event_type == "bid":
            self._log_bid(event, console_output)
        elif event.event_type == "message":
            self._log_message(event, console_output)
        elif event.event_type == "system_decision":
            self._log_system_decision(event, console_output)
        elif event.event_type == "meta_update":
            self._log_meta_update(event, console_output)
        elif event.event_type == "game_end":
            self._log_game_end(event, console_output)
    
    def _log_detailed(self, event: LogEvent):
        """Add event to detailed JSON log"""
        if not self.first_detailed_entry:
            self.detailed_file.write(",\n")
        else:
            self.first_detailed_entry = False
        
        entry = {
            "turn": event.turn,
            "phase": event.event_type,
            **event.data
        }
        
        json.dump(entry, self.detailed_file, ensure_ascii=False, indent=2)
        self.detailed_file.flush()
    
    def _log_setup(self, event: SetupEvent, console_output: bool):
        """Log game setup"""
        roles = event.data["roles"]
        
        # Summary log
        self.summary_file.write("GAME SETUP:\n")
        for player, role in roles.items():
            self.summary_file.write(f"  {player}: {role}\n")
        self.summary_file.write("\n")
        self.summary_file.flush()
        
        # Console output
        if console_output:
            print(f"\nRole Assignments: {json.dumps(roles, ensure_ascii=False)}")
    
    def _log_bid(self, event: BidEvent, console_output: bool):
        """Log bidding event (detailed only, no summary/console for bids)"""
        pass  # Bids are only logged to detailed log
    
    def _log_message(self, event: MessageEvent, console_output: bool):
        """Log message execution"""
        data = event.data
        turn = event.turn
        speaker = data["speaker"]
        recipients = data["recipients"]
        message = data["message"]
        is_dm = data["is_dm"]
        
        # Summary log
        if is_dm:
            recipients_str = ",".join(recipients)
            self.summary_file.write(f"[{turn:02d}] {speaker}▶DM({recipients_str}): {message}\n")
        else:
            self.summary_file.write(f"[{turn:02d}] {speaker}▶ALL: {message}\n")
        self.summary_file.flush()
        
        # Console output
        if console_output:
            if is_dm:
                recipients_str = ",".join(recipients)
                print(f"[{turn:02d}] {speaker}▶DM({recipients_str}): {message}")
            else:
                print(f"[{turn:02d}] {speaker}▶ALL: {message}")
    
    def _log_system_decision(self, event: SystemDecisionEvent, console_output: bool):
        """Log system decision"""
        if console_output:
            system_response = event.data["system_response"]
            reason = system_response.get("reason", "No reason provided")
            print(f"[{event.turn:02d}] System: {reason}")
    
    def _log_meta_update(self, event: MetaUpdateEvent, console_output: bool):
        """Log meta information updates"""
        data = event.data
        turn = event.turn
        public_changes = data["public_changes"]
        private_changes = data["private_changes"]
        
        # Console output
        if console_output and (public_changes or private_changes):
            print(f"[{turn:02d}] System Meta Update:")
            if public_changes:
                print(f"  Public: {public_changes}")
            if private_changes:
                print(f"  Private: {private_changes}")
    
    def _log_game_end(self, event: GameEndEvent, console_output: bool):
        """Log game end"""
        data = event.data
        winner = data["winner"]
        total_turns = data["total_turns"]
        completed = data["completed"]
        
        # Summary log
        if completed:
            self.summary_file.write(f"\nGAME RESULT: Winner = {winner}\n")
        else:
            self.summary_file.write(f"\nGAME INCOMPLETE: Reached maximum turns ({total_turns})\n")
        self.summary_file.flush()
        
        # Console output
        if console_output:
            if completed:
                print(f"*** Game End. Winner = {winner} ***")
            else:
                print(f"*** Game reached maximum turns ({total_turns}) without a winner ***")
    
    def log_initial_meta(self, meta_pub: Dict[str, Any], meta_priv_all: Dict[str, Any]):
        """Log initial meta information"""
        print(f"\nInitial Meta Information:")
        print(f"Public Meta: {json.dumps(meta_pub, ensure_ascii=False)}")
        print(f"Private Meta: {json.dumps(meta_priv_all, ensure_ascii=False)}")
    
    def save_logs(self):
        """Close and finalize all log files"""
        try:
            # Close JSON array for detailed log
            self.detailed_file.write("\n]\n")
            self.detailed_file.close()
            
            # Close summary log
            self.summary_file.write("\n=== END OF GAME ===\n")
            self.summary_file.close()
        except Exception as e:
            print(f"Warning: Error closing log files: {e}")
    
    def __del__(self):
        """Ensure files are closed when object is destroyed"""
        try:
            if hasattr(self, 'detailed_file') and not self.detailed_file.closed:
                self.detailed_file.write("\n]\n")
                self.detailed_file.close()
            if hasattr(self, 'summary_file') and not self.summary_file.closed:
                self.summary_file.close()
        except:
            pass


class ConsoleLogger:
    """Simple console-only logger for debugging"""
    
    @staticmethod
    def log_info(message: str):
        """Log info message"""
        print(message)
    
    @staticmethod
    def log_bids(turn: int, bids: Dict[str, float], pkgs: Dict[str, dict]):
        """Log bidding results (debug only)"""
        print(f"[{turn:02d}] Bids: {bids}")
    
    @staticmethod
    def log_meta_state(turn: int, meta_pub: Dict[str, Any], meta_priv_all: Dict[str, Any]):
        """Log current meta state (debug only)"""
        print(f"[{turn:02d}] Current Meta - Public: {meta_pub}, Private: {meta_priv_all}")
    
    @staticmethod
    def log_error(message: str):
        """Log error message"""
        print(f"Error: {message}")
    
    @staticmethod
    def log_warning(message: str):
        """Log warning message"""
        print(f"Warning: {message}") 