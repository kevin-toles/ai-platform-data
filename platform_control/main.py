#!/usr/bin/env python3
"""
AI Platform Control Panel

Desktop application to manage the AI platform services and models.

Features:
- Start/Stop/Restart Docker containers
- Start/Stop inference-service (native for Metal acceleration)
- Load/Unload LLM models
- Health status monitoring
- Toggle Docker/Native mode per service

Usage:
    python main.py
    
Or double-click: platform_control.command
"""

import customtkinter as ctk
import subprocess
import threading
import json
import os
from pathlib import Path
from typing import Optional, Callable
import httpx

# =============================================================================
# Configuration
# =============================================================================

POC_ROOT = Path(__file__).parent.parent.parent  # /Users/kevintoles/POC
CONFIG_FILE = Path(__file__).parent / "config.json"

# Default service definitions - Kitchen Brigade Architecture
# Reference: ai-platform-data/docs/NETWORK_ARCHITECTURE.md
DEFAULT_SERVICES = {
    "inference-service": {
        "port": 8085,
        "path": POC_ROOT / "inference-service",
        "native_cmd": "./run_native.sh",
        "compose_path": POC_ROOT / "inference-service" / "docker",
        "health_url": "http://localhost:8085/health",
        "supports_native": True,
        "role": "Line Cook",
    },
    "llm-gateway": {
        "port": 8080,
        "container": "llm-gateway-standalone",
        "compose_path": POC_ROOT / "llm-gateway",
        "health_url": "http://localhost:8080/health",
        "supports_native": False,
        "role": "Maître d'",
    },
    "ai-agents": {
        "port": 8082,
        "container": "ai-agents",
        "compose_path": POC_ROOT / "ai-agents",
        "health_url": "http://localhost:8082/health",
        "supports_native": False,
        "role": "Expeditor",
    },
    "code-orchestrator": {
        "port": 8083,
        "container": "code-orchestrator-service",
        "compose_path": POC_ROOT / "Code-Orchestrator-Service",
        "health_url": "http://localhost:8083/health",
        "supports_native": False,
        "role": "Sous Chef",
    },
    "semantic-search": {
        "port": 8081,
        "container": "semantic-search-service",
        "compose_path": POC_ROOT / "semantic-search-service",
        "health_url": "http://localhost:8081/health",
        "supports_native": False,
        "role": "Cookbook",
    },
    "audit-service": {
        "port": 8084,
        "container": "audit-service",
        "compose_path": POC_ROOT / "audit-service",
        "health_url": "http://localhost:8084/health",
        "supports_native": False,
        "role": "Auditor",
    },
}

INFERENCE_API = "http://localhost:8085"


def load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"services": {}, "ui": {"refresh_interval_seconds": 5, "theme": "dark"}}


def save_config(config: dict):
    """Save configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# Service definitions (alias for DEFAULT_SERVICES)
SERVICES = DEFAULT_SERVICES


# =============================================================================
# Theme Configuration
# =============================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =============================================================================
# Service Manager
# =============================================================================

class ServiceManager:
    """Manages service lifecycle operations."""
    
    @staticmethod
    def check_health(url: str, timeout: float = 2.0) -> tuple[bool, str]:
        """Check if service is healthy."""
        try:
            response = httpx.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                return True, status
            return False, f"HTTP {response.status_code}"
        except httpx.ConnectError:
            return False, "Not running"
        except Exception as e:
            return False, str(e)[:30]
    
    @staticmethod
    def start_docker_service(compose_path: Path) -> tuple[bool, str]:
        """Start a Docker Compose service."""
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--build"],
                cwd=compose_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for builds
            )
            if result.returncode == 0:
                return True, "Started"
            # Show more of the error
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, error_msg[-200:] if len(error_msg) > 200 else error_msg
        except subprocess.TimeoutExpired:
            return False, "Timeout - build may still be running"
        except Exception as e:
            return False, str(e)[:100]
    
    @staticmethod
    def stop_docker_service(compose_path: Path) -> tuple[bool, str]:
        """Stop a Docker Compose service."""
        try:
            result = subprocess.run(
                ["docker-compose", "down"],
                cwd=compose_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, "Stopped"
            return False, result.stderr[:100]
        except Exception as e:
            return False, str(e)[:50]
    
    @staticmethod
    def start_native_service(path: Path, cmd: str) -> tuple[bool, str]:
        """Start a native (non-Docker) service."""
        try:
            # Start in background
            subprocess.Popen(
                cmd,
                shell=True,
                cwd=path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, "Starting..."
        except Exception as e:
            return False, str(e)[:50]
    
    @staticmethod
    def stop_native_service(port: int) -> tuple[bool, str]:
        """Stop a native service by killing the process on port."""
        try:
            # Find PID using lsof
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                return True, "Stopped"
            return True, "Not running"
        except Exception as e:
            return False, str(e)[:50]


# =============================================================================
# Model Manager
# =============================================================================

class ModelManager:
    """Manages LLM models via inference-service API."""
    
    @staticmethod
    def list_models() -> list[dict]:
        """Get list of available models."""
        try:
            response = httpx.get(f"{INFERENCE_API}/v1/models", timeout=5.0)
            if response.status_code == 200:
                return response.json().get("data", [])
            return []
        except Exception:
            return []
    
    @staticmethod
    def load_model(model_id: str) -> tuple[bool, str]:
        """Load a model."""
        try:
            response = httpx.post(
                f"{INFERENCE_API}/v1/models/{model_id}/load",
                timeout=120.0,  # Model loading can take time
            )
            if response.status_code == 200:
                return True, "Loaded"
            return False, response.text[:50]
        except Exception as e:
            return False, str(e)[:50]
    
    @staticmethod
    def unload_model(model_id: str) -> tuple[bool, str]:
        """Unload a model."""
        try:
            response = httpx.post(
                f"{INFERENCE_API}/v1/models/{model_id}/unload",
                timeout=30.0,
            )
            if response.status_code == 200:
                return True, "Unloaded"
            return False, response.text[:50]
        except Exception as e:
            return False, str(e)[:50]


# =============================================================================
# UI Components
# =============================================================================

class ServiceCard(ctk.CTkFrame):
    """Card displaying a single service status and controls."""
    
    def __init__(
        self,
        parent,
        service_name: str,
        service_config: dict,
        app_config: dict,
        on_config_change: Callable,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        
        self.service_name = service_name
        self.config = service_config
        self.app_config = app_config
        self.on_config_change = on_config_change
        self.is_running = False
        
        # Get current mode from config
        svc_config = app_config.get("services", {}).get(service_name, {})
        self.use_docker = svc_config.get("mode", "docker") == "docker"
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            self,
            text="●",
            font=("Helvetica", 20),
            text_color="gray",
            width=30,
        )
        self.status_indicator.grid(row=0, column=0, padx=(10, 5), pady=10)
        
        # Service name and status
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="w", padx=5, pady=10)
        
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=service_name,
            font=("Helvetica", 14, "bold"),
        )
        self.name_label.pack(anchor="w")
        
        self.status_label = ctk.CTkLabel(
            info_frame,
            text=f"Port {service_config['port']} • Checking...",
            font=("Helvetica", 11),
            text_color="gray",
        )
        self.status_label.pack(anchor="w")
        
        # Control buttons and Docker checkbox
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=10, pady=10)
        
        # Docker checkbox (only show if service supports native mode)
        if service_config.get("supports_native", False):
            self.docker_var = ctk.BooleanVar(value=self.use_docker)
            self.docker_checkbox = ctk.CTkCheckBox(
                btn_frame,
                text="Docker",
                variable=self.docker_var,
                width=70,
                height=20,
                font=("Helvetica", 10),
                command=self._on_docker_toggle,
            )
            self.docker_checkbox.pack(side="left", padx=(0, 8))
        else:
            self.docker_var = ctk.BooleanVar(value=True)  # Always Docker
        
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="Start",
            width=60,
            height=28,
            command=self.start_service,
        )
        self.start_btn.pack(side="left", padx=2)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="Stop",
            width=60,
            height=28,
            fg_color="#c92a1e",
            hover_color="#a82318",
            command=self.stop_service,
        )
        self.stop_btn.pack(side="left", padx=2)
    
    def _on_docker_toggle(self):
        """Handle Docker checkbox toggle."""
        self.use_docker = self.docker_var.get()
        
        # Update config
        if "services" not in self.app_config:
            self.app_config["services"] = {}
        if self.service_name not in self.app_config["services"]:
            self.app_config["services"][self.service_name] = {}
        
        self.app_config["services"][self.service_name]["mode"] = "docker" if self.use_docker else "native"
        self.on_config_change()
        
        # Update status label to indicate restart needed
        mode_text = "Docker" if self.use_docker else "Native"
        self.status_label.configure(
            text=f"Port {self.config['port']} • Mode: {mode_text} (restart to apply)",
            text_color="orange",
        )
    
    def update_status(self, is_running: bool, status_text: str):
        """Update the visual status."""
        self.is_running = is_running
        mode_text = "Docker" if self.use_docker else "Native"
        
        if is_running:
            self.status_indicator.configure(text_color="#4CAF50")  # Green
            self.status_label.configure(
                text=f"Port {self.config['port']} • {status_text} ({mode_text})",
                text_color="#4CAF50",
            )
        else:
            self.status_indicator.configure(text_color="#f44336")  # Red
            self.status_label.configure(
                text=f"Port {self.config['port']} • {status_text} ({mode_text})",
                text_color="#f44336",
            )
    
    def start_service(self):
        """Start the service."""
        self.status_label.configure(text="Starting...", text_color="orange")
        
        def _start():
            if self.use_docker:
                success, msg = ServiceManager.start_docker_service(
                    self.config["compose_path"]
                )
            else:
                success, msg = ServiceManager.start_native_service(
                    self.config.get("path", self.config["compose_path"]),
                    self.config.get("native_cmd", "./run_native.sh"),
                )
            
            # Update UI in main thread
            self.after(100, lambda: self._post_action(success, msg))
        
        threading.Thread(target=_start, daemon=True).start()
    
    def stop_service(self):
        """Stop the service."""
        self.status_label.configure(text="Stopping...", text_color="orange")
        
        def _stop():
            if self.use_docker:
                success, msg = ServiceManager.stop_docker_service(
                    self.config["compose_path"]
                )
            else:
                success, msg = ServiceManager.stop_native_service(
                    self.config["port"]
                )
            
            self.after(100, lambda: self._post_action(success, msg))
        
        threading.Thread(target=_stop, daemon=True).start()
    
    def _post_action(self, success: bool, msg: str):
        """Update UI after action."""
        if success:
            self.status_label.configure(text=msg, text_color="gray")
        else:
            self.status_label.configure(text=f"Error: {msg}", text_color="orange")


class ModelCard(ctk.CTkFrame):
    """Card displaying a single model status and controls."""
    
    def __init__(
        self,
        parent,
        model_data: dict,
        on_update: Callable,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        
        self.model_id = model_data["id"]
        self.model_data = model_data
        self.on_update = on_update
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        status = model_data.get("status", "unknown")
        color = "#4CAF50" if status == "loaded" else "gray"
        
        self.status_indicator = ctk.CTkLabel(
            self,
            text="●",
            font=("Helvetica", 16),
            text_color=color,
            width=25,
        )
        self.status_indicator.grid(row=0, column=0, padx=(10, 5), pady=8)
        
        # Model info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="w", padx=5, pady=8)
        
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=self.model_id,
            font=("Helvetica", 12, "bold"),
        )
        self.name_label.pack(anchor="w")
        
        memory = model_data.get("memory_mb", 0)
        roles = ", ".join(model_data.get("roles", []))
        self.info_label = ctk.CTkLabel(
            info_frame,
            text=f"{memory}MB • {roles}",
            font=("Helvetica", 10),
            text_color="gray",
        )
        self.info_label.pack(anchor="w")
        
        # Load/Unload button
        if status == "loaded":
            btn_text = "Unload"
            btn_color = "#c92a1e"
            btn_hover = "#a82318"
            btn_command = self.unload_model
        else:
            btn_text = "Load"
            btn_color = None  # Default
            btn_hover = None
            btn_command = self.load_model
        
        self.action_btn = ctk.CTkButton(
            self,
            text=btn_text,
            width=70,
            height=26,
            font=("Helvetica", 11),
            fg_color=btn_color,
            hover_color=btn_hover,
            command=btn_command,
        )
        self.action_btn.grid(row=0, column=2, padx=10, pady=8)
    
    def load_model(self):
        """Load the model."""
        self.action_btn.configure(text="Loading...", state="disabled")
        
        def _load():
            success, msg = ModelManager.load_model(self.model_id)
            self.after(100, self.on_update)
        
        threading.Thread(target=_load, daemon=True).start()
    
    def unload_model(self):
        """Unload the model."""
        self.action_btn.configure(text="...", state="disabled")
        
        def _unload():
            success, msg = ModelManager.unload_model(self.model_id)
            self.after(100, self.on_update)
        
        threading.Thread(target=_unload, daemon=True).start()


# =============================================================================
# Main Application
# =============================================================================

class PlatformControlApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("AI Platform Control")
        self.geometry("500x700")
        self.minsize(450, 600)
        
        # Load config
        self.config = load_config()
        
        # Store service cards for updates
        self.service_cards: dict[str, ServiceCard] = {}
        self.model_cards: list[ModelCard] = []
        
        self._create_ui()
        self._start_health_monitor()
    
    def _create_ui(self):
        """Create the UI layout."""
        # Main scrollable container
        main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title = ctk.CTkLabel(
            main_scroll,
            text="🤖 AI Platform Control",
            font=("Helvetica", 20, "bold"),
        )
        title.pack(pady=(0, 15))
        
        # Services Section
        services_label = ctk.CTkLabel(
            main_scroll,
            text="Services (Kitchen Brigade)",
            font=("Helvetica", 14, "bold"),
            anchor="w",
        )
        services_label.pack(fill="x", pady=(10, 5))
        
        services_frame = ctk.CTkFrame(main_scroll)
        services_frame.pack(fill="x", pady=(0, 15))
        
        for name, svc_config in SERVICES.items():
            card = ServiceCard(
                services_frame,
                name,
                svc_config,
                self.config,
                self._save_config,
            )
            card.pack(fill="x", padx=5, pady=3)
            self.service_cards[name] = card
        
        # Quick Actions
        actions_frame = ctk.CTkFrame(main_scroll, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 15))
        
        start_all_btn = ctk.CTkButton(
            actions_frame,
            text="▶ Start All",
            width=120,
            command=self._start_all_services,
        )
        start_all_btn.pack(side="left", padx=5)
        
        stop_all_btn = ctk.CTkButton(
            actions_frame,
            text="■ Stop All",
            width=120,
            fg_color="#c92a1e",
            hover_color="#a82318",
            command=self._stop_all_services,
        )
        stop_all_btn.pack(side="left", padx=5)
        
        refresh_btn = ctk.CTkButton(
            actions_frame,
            text="↻ Refresh",
            width=100,
            fg_color="gray",
            command=self._refresh_all,
        )
        refresh_btn.pack(side="right", padx=5)
        
        # Models Section
        models_label = ctk.CTkLabel(
            main_scroll,
            text="LLM Models (inference-service)",
            font=("Helvetica", 14, "bold"),
            anchor="w",
        )
        models_label.pack(fill="x", pady=(10, 5))
        
        self.models_frame = ctk.CTkFrame(main_scroll)
        self.models_frame.pack(fill="x", pady=(0, 10))
        
        self._refresh_models()
        
        # Status bar (fixed at bottom of scroll area)
        self.status_bar = ctk.CTkLabel(
            main_scroll,
            text="Ready",
            font=("Helvetica", 10),
            text_color="gray",
        )
        self.status_bar.pack(fill="x", pady=(10, 0))
    
    def _start_health_monitor(self):
        """Start background health monitoring."""
        def _monitor():
            while True:
                for name, card in self.service_cards.items():
                    config = SERVICES[name]
                    is_healthy, status = ServiceManager.check_health(
                        config["health_url"]
                    )
                    card.after(0, lambda c=card, h=is_healthy, s=status: c.update_status(h, s))
                
                threading.Event().wait(5.0)  # Check every 5 seconds
        
        threading.Thread(target=_monitor, daemon=True).start()
    
    def _refresh_models(self):
        """Refresh the models list."""
        # Clear existing
        for card in self.model_cards:
            card.destroy()
        self.model_cards.clear()
        
        # Get models
        models = ModelManager.list_models()
        
        if not models:
            label = ctk.CTkLabel(
                self.models_frame,
                text="No models available (inference-service not running?)",
                text_color="gray",
            )
            label.pack(pady=20)
            return
        
        for model in models:
            card = ModelCard(
                self.models_frame,
                model,
                on_update=self._refresh_models,
            )
            card.pack(fill="x", padx=5, pady=2)
            self.model_cards.append(card)
    
    def _start_all_services(self):
        """Start all services."""
        self.status_bar.configure(text="Starting all services...")
        for card in self.service_cards.values():
            card.start_service()
    
    def _stop_all_services(self):
        """Stop all services."""
        self.status_bar.configure(text="Stopping all services...")
        for card in self.service_cards.values():
            card.stop_service()
    
    def _save_config(self):
        """Save current configuration to disk."""
        save_config(self.config)
        self.status_bar.configure(text="Config saved")
    
    def _refresh_all(self):
        """Refresh all status."""
        self.status_bar.configure(text="Refreshing...")
        self._refresh_models()
        self.status_bar.configure(text="Ready")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app = PlatformControlApp()
    app.mainloop()
