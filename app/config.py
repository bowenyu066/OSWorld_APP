"""Configuration management for the Annotator Kit."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration model."""
    vmx_path: str = Field("D:/VMs/Win11/Win11.vmx", description="Path to VMware .vmx file")
    guest_username: str = Field("user", description="Guest VM username")
    guest_password: str = Field("password", description="Guest VM password")
    tasks_dir: str = Field("./tasks/samples", description="Directory containing task JSON files")
    output_dir: str = Field("./runs", description="Output directory for task results")
    vmware_bin: str = Field("C:/Program Files (x86)/VMware/VMware Workstation", description="VMware installation directory")
    start_fullscreen: bool = Field(True, description="Start VM in fullscreen mode")
    snapshot_name: str = Field("clean", description="Default snapshot name to revert to")
    use_snapshots: bool = Field(True, description="Whether to use snapshot revert before tasks")
    # Auto-login removed - VM configured with dedicated auto-login software


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> AppConfig:
        """Load configuration from file or create default."""
        if not self.config_path.exists():
            # Create default configuration
            default_config = AppConfig()
            self._save_config(default_config)
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return AppConfig(**data)
        except Exception as e:
            print(f"Error loading config: {e}")
            print("Using default configuration")
            return AppConfig()
    
    def _save_config(self, config: AppConfig) -> None:
        """Save configuration to file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
    
    def get_vmrun_path(self) -> str:
        """Get the path to vmrun.exe."""
        return os.path.join(self.config.vmware_bin, "vmrun.exe")
    
    def get_vmware_path(self) -> str:
        """Get the path to vmware.exe."""
        return os.path.join(self.config.vmware_bin, "vmware.exe")
    
    def get_tasks_dir(self) -> Path:
        """Get the tasks directory as a Path object."""
        return Path(self.config.tasks_dir).resolve()
    
    def get_output_dir(self) -> Path:
        """Get the output directory as a Path object."""
        return Path(self.config.output_dir).resolve()


# Global config instance
config_manager = ConfigManager()
