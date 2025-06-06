"""
Image generation module for social deduction game assets.
Generates role card images and game manual covers using OpenAI's DALL-E API.
"""

import os
import json
import requests
from typing import Optional, Dict, Any
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI library not installed. Install with: pip install openai")
    OpenAI = None

class GameImageGenerator:
    """Generate images for social deduction game components."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the image generator with OpenAI API key."""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        if OpenAI is None:
            raise ImportError("OpenAI library not installed. Install with: pip install openai")
            
        self.client = OpenAI(api_key=self.api_key)
        
    def generate_role_image(self, 
                          role_name: str, 
                          role_description: str,
                          game_theme: str = "medieval fantasy",
                          style: str = "digital art",
                          output_dir: str = ".",
                          size: str = "1024x1024") -> Optional[str]:
        """
        Generate an image for a specific role.
        
        Args:
            role_name: Name of the role
            role_description: Description of the role and abilities
            game_theme: Overall theme of the game
            style: Art style for the image
            output_dir: Directory to save the image
            size: Image size (256x256, 512x512, or 1024x1024)
            
        Returns:
            Path to the generated image file, or None if generation failed
        """
        # Create a detailed prompt for the role
        prompt = self._create_role_prompt(role_name, role_description, game_theme, style)
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            
            # Download and save the image
            filename = f"{role_name.lower().replace(' ', '_')}_card.png"
            filepath = os.path.join(output_dir, filename)
            
            if self._download_image(image_url, filepath):
                print(f"Generated role image: {filepath}")
                return filepath
            else:
                print(f"Failed to download image for {role_name}")
                return None
                
        except Exception as e:
            print(f"Error generating image for {role_name}: {e}")
            return None
    
    def generate_cover_image(self,
                           game_title: str,
                           game_description: str,
                           theme: str = "medieval fantasy",
                           style: str = "epic fantasy book cover",
                           output_dir: str = ".",
                           size: str = "1024x1024") -> Optional[str]:
        """
        Generate a cover image for the game manual.
        
        Args:
            game_title: Title of the game
            game_description: Brief description of the game
            theme: Theme of the game
            style: Art style for the cover
            output_dir: Directory to save the image
            size: Image size
            
        Returns:
            Path to the generated image file, or None if generation failed
        """
        prompt = self._create_cover_prompt(game_title, game_description, theme, style)
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            
            # Download and save the image
            filename = "cover_image.png"
            filepath = os.path.join(output_dir, filename)
            
            if self._download_image(image_url, filepath):
                print(f"Generated cover image: {filepath}")
                return filepath
            else:
                print("Failed to download cover image")
                return None
                
        except Exception as e:
            print(f"Error generating cover image: {e}")
            return None
    
    def generate_game_assets(self,
                           game_config: Dict[str, Any],
                           output_dir: str = ".") -> Dict[str, str]:
        """
        Generate all images for a game (cover + role cards).
        
        Args:
            game_config: Configuration dictionary containing game info and roles
            output_dir: Directory to save all images
            
        Returns:
            Dictionary mapping asset names to file paths
        """
        generated_assets = {}
        
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(exist_ok=True)
        
        # Generate cover image
        cover_path = self.generate_cover_image(
            game_config.get('title', 'Social Deduction Game'),
            game_config.get('description', ''),
            game_config.get('theme', 'medieval fantasy'),
            output_dir=output_dir
        )
        
        if cover_path:
            generated_assets['cover'] = cover_path
        
        # Generate role images
        roles = game_config.get('roles', [])
        for role in roles:
            role_name = role.get('name', '')
            role_desc = role.get('description', '')
            
            if role_name:
                role_path = self.generate_role_image(
                    role_name,
                    role_desc,
                    game_config.get('theme', 'medieval fantasy'),
                    output_dir=output_dir
                )
                
                if role_path:
                    generated_assets[f'role_{role_name.lower()}'] = role_path
                
                # Small delay to avoid rate limiting
                time.sleep(1)
        
        return generated_assets
    
    def _create_role_prompt(self, role_name: str, role_description: str, theme: str, style: str) -> str:
        """Create a detailed prompt for role image generation."""
        base_prompt = f"A {style} illustration of a {role_name} character in a {theme} setting. "
        
        # Add role-specific details
        role_details = f"The character embodies the role of {role_name}: {role_description}. "
        
        # Add artistic direction
        artistic_details = (
            "The image should be suitable for a game card, with clear composition, "
            "detailed character design, and atmospheric lighting. "
            "Focus on the character's distinctive features and personality. "
            "The background should complement but not overwhelm the character. "
            "High quality, professional game art style."
        )
        
        return base_prompt + role_details + artistic_details
    
    def _create_cover_prompt(self, title: str, description: str, theme: str, style: str) -> str:
        """Create a detailed prompt for cover image generation."""
        base_prompt = f"A {style} for a social deduction game called '{title}'. "
        
        game_details = f"The game is about: {description}. "
        
        theme_details = f"The setting is {theme}. "
        
        artistic_details = (
            "The cover should be mysterious and engaging, evoking themes of deception, "
            "strategy, and hidden identities. Include multiple shadowy figures or silhouettes, "
            "suggesting hidden roles and secret agendas. "
            "Use dramatic lighting and composition typical of high-quality game covers. "
            "The mood should be suspenseful and intriguing. "
            "Leave space for text overlay. Professional game cover quality."
        )
        
        return base_prompt + game_details + theme_details + artistic_details
    
    def _download_image(self, url: str, filepath: str) -> bool:
        """Download an image from URL and save to filepath."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return True
        except Exception as e:
            print(f"Error downloading image: {e}")
            return False

def create_game_config_from_rules(rules_file: str) -> Dict[str, Any]:
    """
    Extract game configuration from a rules file for image generation.
    
    Args:
        rules_file: Path to the Python rules file
        
    Returns:
        Configuration dictionary suitable for image generation
    """
    config = {
        'title': 'Unknown Game',
        'description': 'A social deduction game',
        'theme': 'medieval fantasy',
        'roles': []
    }
    
    try:
        # Read the rules file to extract information
        with open(rules_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Try to extract game title and description from comments or variables
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Look for title in comments or variables
            if 'GAME_TITLE' in line or 'game_title' in line:
                if '=' in line:
                    title = line.split('=', 1)[1].strip().strip('"\'')
                    if title:
                        config['title'] = title
            
            # Look for description
            if 'GAME_DESCRIPTION' in line or 'game_description' in line:
                if '=' in line:
                    desc = line.split('=', 1)[1].strip().strip('"\'')
                    if desc:
                        config['description'] = desc
        
        # Extract role information from ROLES dictionary or similar structures
        if 'ROLES = {' in content or 'roles = {' in content:
            # This is a simplified extraction - in practice, you might want to
            # actually import and inspect the module
            import re
            role_pattern = r'["\']([^"\']+)["\']\s*:\s*{[^}]*["\']description["\']\s*:\s*["\']([^"\']+)["\']'
            matches = re.findall(role_pattern, content)
            
            for role_name, role_desc in matches:
                config['roles'].append({
                    'name': role_name,
                    'description': role_desc
                })
    
    except Exception as e:
        print(f"Error parsing rules file: {e}")
    
    return config

# Example usage and testing
if __name__ == "__main__":
    # Example of how to use the image generator
    generator = GameImageGenerator()
    
    # Example game configuration
    game_config = {
        'title': 'Shadows of Deception',
        'description': 'A medieval fantasy social deduction game where players must identify the traitors among them',
        'theme': 'medieval fantasy',
        'roles': [
            {
                'name': 'Knight',
                'description': 'A noble warrior sworn to protect the innocent and root out evil'
            },
            {
                'name': 'Assassin',
                'description': 'A shadowy figure working to eliminate key targets'
            },
            {
                'name': 'Seer',
                'description': 'A mystical oracle who can divine the true nature of others'
            }
        ]
    }
    
    # Generate all assets
    assets = generator.generate_game_assets(game_config, "generated_images")
    print("Generated assets:", assets) 