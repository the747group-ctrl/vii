"""
VII Reminders — Background timer system.
"Remind me in 5 minutes to check the oven."

Developed by The 747 Lab
"""

import threading
import time
import subprocess
import os


class ReminderManager:
    def __init__(self):
        self._reminders = []

    def add(self, message, delay_seconds):
        """Schedule a reminder that fires after delay_seconds."""
        def _fire():
            time.sleep(delay_seconds)
            # macOS notification
            safe_msg = message.replace('"', '\\"')
            subprocess.Popen(["osascript", "-e",
                f'display notification "{safe_msg}" with title "VII Reminder" sound name "Glass"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Also speak it
            subprocess.Popen(["say", "-v", "Daniel", f"Reminder: {message}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        t = threading.Thread(target=_fire, daemon=True)
        t.start()
        self._reminders.append({"message": message, "delay": delay_seconds, "thread": t})
        return True

    def parse_delay(self, text):
        """Parse '5 minutes', '1 hour', '30 seconds' into seconds."""
        import re
        text = text.lower().strip()

        patterns = [
            (r'(\d+)\s*seconds?', 1),
            (r'(\d+)\s*min(?:ute)?s?', 60),
            (r'(\d+)\s*hours?', 3600),
            (r'half\s+(?:an?\s+)?hour', None),
        ]

        for pattern, multiplier in patterns:
            match = re.search(pattern, text)
            if match:
                if multiplier is None:
                    return 1800  # half hour
                return int(match.group(1)) * multiplier

        return None


# Global instance
reminders = ReminderManager()
