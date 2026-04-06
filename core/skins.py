"""
VII Skin System — Customizable orb appearance.

Load skins from config/skins.json. Each skin defines:
- Size, shape, colors per state
- Glow intensity and style
- Optional avatar image overlay

Usage:
    from core.skins import SkinManager
    manager = SkinManager()
    skin = manager.active_skin()
    color = skin.color_for_state("listening")

Developed by The 747 Lab
"""

import json
import os
from dataclasses import dataclass, field

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "skins.json")


@dataclass
class Skin:
    name: str = "Classic Orb"
    skin_type: str = "orb"
    size: int = 72
    colors: dict = field(default_factory=lambda: {
        "idle": "#06b6d4",
        "listening": "#ef4444",
        "thinking": "#8b5cf6",
        "speaking": "#06b6d4",
    })
    glow: bool = True
    glow_intensity: float = 1.0
    avatar_image: str = ""  # path to overlay image (optional)

    def color_for_state(self, state: str) -> str:
        return self.colors.get(state, self.colors.get("idle", "#06b6d4"))


class SkinManager:
    def __init__(self, config_path: str = CONFIG_PATH):
        self._config_path = config_path
        self._skins = {}
        self._active = "orb"
        self._load()

    def _load(self):
        if not os.path.exists(self._config_path):
            self._skins = {"orb": Skin()}
            return
        with open(self._config_path) as f:
            data = json.load(f)
        self._active = data.get("active_skin", "orb")
        for name, cfg in data.get("skins", {}).items():
            self._skins[name] = Skin(
                name=cfg.get("name", name),
                skin_type=cfg.get("type", "orb"),
                size=cfg.get("size", 72),
                colors=cfg.get("colors", {}),
                glow=cfg.get("glow", True),
                glow_intensity=cfg.get("glow_intensity", 1.0),
                avatar_image=cfg.get("avatar_image", ""),
            )
        if not self._skins:
            self._skins = {"orb": Skin()}

    def active_skin(self) -> Skin:
        return self._skins.get(self._active, Skin())

    def list_skins(self) -> list:
        return [(name, skin.name) for name, skin in self._skins.items()]

    def set_active(self, name: str) -> bool:
        if name not in self._skins:
            return False
        self._active = name
        self._save()
        return True

    def _save(self):
        if not os.path.exists(self._config_path):
            return
        with open(self._config_path) as f:
            data = json.load(f)
        data["active_skin"] = self._active
        with open(self._config_path, "w") as f:
            json.dump(data, f, indent=2)
