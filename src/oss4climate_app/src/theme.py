"""
Theme configuration for the OSS4Climate frontend.

This module provides a centralized configuration for all design colors and theme settings.
The CSS uses these values through Jinja2 templating to generate CSS variables.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ThemeColors:
    """Color palette for the application theme."""

    # Primary colors
    primary: str = "#2e8b57"  # Sea green - main brand color
    primary_light: str = "#e8f5e9"  # Light green for backgrounds
    primary_dark: str = "#1b5e20"  # Dark green for text/accents

    # Secondary colors
    secondary: str = "#3498db"  # Blue for links/accents
    secondary_light: str = "#e3f2fd"  # Light blue

    # Neutral colors
    background: str = "#f9f9f9"  # Page background
    surface: str = "#ffffff"  # Card/container background
    text_primary: str = "#333333"  # Primary text
    text_secondary: str = "#666666"  # Secondary text
    text_light: str = "#ffffff"  # Light text (on dark backgrounds)

    # Border and divider colors
    border: str = "#dddddd"  # Light gray for borders
    divider: str = "#eeeeee"  # Very light gray for dividers

    # Status colors
    success: str = "#28a745"  # Green for success states
    warning: str = "#ffc107"  # Yellow for warnings
    error: str = "#dc3545"  # Red for errors
    info: str = "#17a2b8"  # Cyan for info

    # Shadow colors
    shadow_small: str = "rgba(0, 0, 0, 0.1)"  # Small shadow
    shadow_medium: str = "rgba(0, 0, 0, 0.15)"  # Medium shadow
    shadow_large: str = "rgba(0, 0, 0, 0.2)"  # Large shadow


@dataclass
class ThemeTypography:
    """Typography settings for the application."""

    font_family: str = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    font_family_mono: str = "'Courier New', Courier, monospace"

    # Font sizes
    font_size_base: str = "16px"
    font_size_small: str = "14px"
    font_size_large: str = "18px"
    font_size_xlarge: str = "24px"

    # Font weights
    font_weight_normal: int = 400
    font_weight_medium: int = 500
    font_weight_bold: int = 600
    font_weight_heavy: int = 700

    # Line heights
    line_height_base: float = 1.6
    line_height_tight: float = 1.4
    line_height_loose: float = 1.8

    # Letter spacing
    letter_spacing_normal: str = "normal"
    letter_spacing_wide: str = "0.5px"


@dataclass
class ThemeSpacing:
    """Spacing settings for the application."""

    # Base unit (in pixels)
    base: int = 8

    # Spacing scale
    xs: int = 4  # 0.5 * base
    sm: int = 8  # 1 * base
    md: int = 16  # 2 * base
    lg: int = 24  # 3 * base
    xl: int = 32  # 4 * base
    xxl: int = 48  # 6 * base

    # Border radius
    border_radius_sm: int = 4
    border_radius_md: int = 8
    border_radius_lg: int = 12
    border_radius_full: int = 25  # For pills/buttons


@dataclass
class ThemeShadows:
    """Shadow settings for the application."""

    sm: str = "0 1px 2px rgba(0, 0, 0, 0.05)"
    md: str = "0 2px 10px rgba(0, 0, 0, 0.1)"
    lg: str = "0 4px 20px rgba(0, 0, 0, 0.15)"
    xl: str = "0 8px 30px rgba(0, 0, 0, 0.2)"


@dataclass
class ThemeTransitions:
    """Transition settings for the application."""

    fast: str = "0.15s ease"
    normal: str = "0.3s ease"
    slow: str = "0.5s ease"


@dataclass
class Theme:
    """Complete theme configuration."""

    colors: ThemeColors = field(default_factory=ThemeColors)
    typography: ThemeTypography = field(default_factory=ThemeTypography)
    spacing: ThemeSpacing = field(default_factory=ThemeSpacing)
    shadows: ThemeShadows = field(default_factory=ThemeShadows)
    transitions: ThemeTransitions = field(default_factory=ThemeTransitions)

    def to_css_variables(self) -> str:
        """
        Convert the theme configuration to CSS custom properties.

        Returns:
            str: CSS variable declarations for use in <style> tags or CSS files
        """
        variables = []

        # Colors
        variables.append(f"--color-primary: {self.colors.primary};")
        variables.append(f"--color-primary-light: {self.colors.primary_light};")
        variables.append(f"--color-primary-dark: {self.colors.primary_dark};")
        variables.append(f"--color-secondary: {self.colors.secondary};")
        variables.append(f"--color-secondary-light: {self.colors.secondary_light};")
        variables.append(f"--color-background: {self.colors.background};")
        variables.append(f"--color-surface: {self.colors.surface};")
        variables.append(f"--color-text-primary: {self.colors.text_primary};")
        variables.append(f"--color-text-secondary: {self.colors.text_secondary};")
        variables.append(f"--color-text-light: {self.colors.text_light};")
        variables.append(f"--color-border: {self.colors.border};")
        variables.append(f"--color-divider: {self.colors.divider};")
        variables.append(f"--color-success: {self.colors.success};")
        variables.append(f"--color-warning: {self.colors.warning};")
        variables.append(f"--color-error: {self.colors.error};")
        variables.append(f"--color-info: {self.colors.info};")

        # Typography
        variables.append(f"--font-family: {self.typography.font_family};")
        variables.append(f"--font-family-mono: {self.typography.font_family_mono};")
        variables.append(f"--font-size-base: {self.typography.font_size_base};")
        variables.append(f"--font-size-small: {self.typography.font_size_small};")
        variables.append(f"--font-size-large: {self.typography.font_size_large};")
        variables.append(f"--font-size-xlarge: {self.typography.font_size_xlarge};")
        variables.append(f"--font-weight-normal: {self.typography.font_weight_normal};")
        variables.append(f"--font-weight-medium: {self.typography.font_weight_medium};")
        variables.append(f"--font-weight-bold: {self.typography.font_weight_bold};")
        variables.append(f"--line-height-base: {self.typography.line_height_base};")

        # Spacing
        variables.append(f"--spacing-xs: {self.spacing.xs}px;")
        variables.append(f"--spacing-sm: {self.spacing.sm}px;")
        variables.append(f"--spacing-md: {self.spacing.md}px;")
        variables.append(f"--spacing-lg: {self.spacing.lg}px;")
        variables.append(f"--spacing-xl: {self.spacing.xl}px;")
        variables.append(f"--spacing-xxl: {self.spacing.xxl}px;")

        # Border radius
        variables.append(f"--border-radius-sm: {self.spacing.border_radius_sm}px;")
        variables.append(f"--border-radius-md: {self.spacing.border_radius_md}px;")
        variables.append(f"--border-radius-lg: {self.spacing.border_radius_lg}px;")
        variables.append(f"--border-radius-full: {self.spacing.border_radius_full}px;")

        # Shadows
        variables.append(f"--shadow-sm: {self.shadows.sm};")
        variables.append(f"--shadow-md: {self.shadows.md};")
        variables.append(f"--shadow-lg: {self.shadows.lg};")
        variables.append(f"--shadow-xl: {self.shadows.xl};")

        # Transitions
        variables.append(f"--transition-fast: {self.transitions.fast};")
        variables.append(f"--transition-normal: {self.transitions.normal};")
        variables.append(f"--transition-slow: {self.transitions.slow};")

        return "\n".join(variables)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the theme configuration to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the theme
        """
        return {
            "colors": {
                "primary": self.colors.primary,
                "primary_light": self.colors.primary_light,
                "primary_dark": self.colors.primary_dark,
                "secondary": self.colors.secondary,
                "background": self.colors.background,
                "surface": self.colors.surface,
                "text_primary": self.colors.text_primary,
                "text_secondary": self.colors.text_secondary,
                "text_light": self.colors.text_light,
                "border": self.colors.border,
                "divider": self.colors.divider,
            },
            "typography": {
                "font_family": self.typography.font_family,
                "font_size_base": self.typography.font_size_base,
            },
            "spacing": {
                "base": self.spacing.base,
                "sm": self.spacing.sm,
                "md": self.spacing.md,
                "lg": self.spacing.lg,
            },
        }


# Default theme instance
THEME = Theme()
