"""
Image generation module for social deduction games using OpenAI's DALL-E API.
Generates cover art, role card images, and other game assets.
"""

import os
import requests
import json
from typing import Dict, List, Optional, Tuple
import re
from openai import OpenAI


class GameImageGenerator:
    """Generates images for social deduction games using OpenAI's DALL-E API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the image generator.
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Style presets for different types of images
        self.style_presets = {
            'cover': "dramatic illustration style, atmospheric lighting, mysterious mood, cinematic composition",
            'role_card': "character portrait, fantasy art style, detailed face, atmospheric background",
            'icon': "simple icon design, clean lines, symbolic representation",
            'background': "atmospheric background, subtle textures, game art style"
        }
    
    def generate_image(self, prompt: str, style: str = 'cover', size: str = "1024x1024") -> Optional[str]:
        """Generate a single image using DALL-E.
        
        Args:
            prompt: Description of the image to generate
            style: Style preset to use ('cover', 'role_card', 'icon', 'background')
            size: Image size (1024x1024, 1024x1792, or 1792x1024)
            
        Returns:
            URL of the generated image, or None if generation failed
        """
        try:
            # Combine prompt with style preset
            full_prompt = f"{prompt}, {self.style_presets.get(style, '')}"
            print(f"DALL-E prompt: {full_prompt[:150]}...")
            
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size=size,
                quality="standard",
                n=1,
            )
            
            if response and response.data and len(response.data) > 0:
                url = response.data[0].url
                print(f"Successfully generated image URL: {url[:50]}...")
                return url
            else:
                print("DALL-E response was empty or invalid")
                return None
                
        except Exception as e:
            print(f"Error generating image with DALL-E: {e}")
            print(f"Prompt was: {prompt[:100]}...")
            return None
    
    def download_image(self, url: str, filepath: str) -> bool:
        """Download an image from a URL to a file.
        
        Args:
            url: URL of the image to download
            filepath: Local path to save the image
            
        Returns:
            True if successful, False otherwise
        """
        if not url or url.strip() == "":
            print(f"Error downloading image: URL is empty or None")
            return False
            
        try:
            print(f"Downloading image from {url[:50]}... to {filepath}")
            response = requests.get(url)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            if filepath and os.path.dirname(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"Successfully downloaded image to {filepath}")
            return True
        except Exception as e:
            print(f"Error downloading image from {url}: {e}")
            return False
    
    def generate_cover_image(self, game_config: Dict) -> Optional[str]:
        """Generate a cover image for the game manual.
        
        Args:
            game_config: Dictionary containing game information
            
        Returns:
            Local filepath of the generated cover image, or None if failed
        """
        title = game_config.get('title', 'Social Deduction Game')
        theme = game_config.get('theme', 'mysterious')
        setting = game_config.get('setting', 'fantasy')
        
        prompt = f"Atmospheric illustration for {theme} social deduction game, {setting} environment. Group of mysterious figures in shadows, dramatic lighting, intrigue and suspense atmosphere. Digital artwork, no text, no words, no book elements, pure illustration only, cinematic composition"
        
        print(f"Generating cover image with prompt: {prompt[:100]}...")
        url = self.generate_image(prompt, 'cover', "1024x1024")
        if not url:
            print("Failed to generate cover image URL")
            return None
        
        print(f"Generated cover image URL: {url[:50]}...")
        filepath = "cover_image.png"
        if self.download_image(url, filepath):
            return filepath
        return None
    
    def generate_role_image(self, role_name: str, role_description: str, game_theme: str = 'fantasy') -> Optional[str]:
        """Generate an image for a specific role card.
        
        Args:
            role_name: Name of the role
            role_description: Description of the role's appearance/characteristics
            game_theme: Theme of the game (fantasy, modern, sci-fi, etc.)
            
        Returns:
            Local filepath of the generated role image, or None if failed
        """
        # Create a prompt specifically for pure character illustration without any text elements
        prompt = f"Character portrait illustration, {game_theme} setting, mysterious person. Digital artwork, portrait style, atmospheric lighting. IMPORTANT: absolutely no text, no words, no letters, no writing, no symbols, no labels, no titles anywhere in the image. Pure character art only, clean artwork without any textual elements whatsoever"
        
        url = self.generate_image(prompt, 'role_card', "1024x1024")
        if not url:
            return None
        
        # Clean filename
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', role_name.lower())
        filepath = f"role_{safe_name}.png"
        
        if self.download_image(url, filepath):
            return filepath
        return None
    
    def generate_game_assets(self, game_config: Dict, output_dir: str = ".") -> Dict[str, str]:
        """Generate all image assets for a social deduction game.
        
        Args:
            game_config: Dictionary containing game configuration
            output_dir: Directory to save generated images
            
        Returns:
            Dictionary mapping asset type to filepath
        """
        assets = {}
        original_dir = os.getcwd()
        
        try:
            os.chdir(output_dir)
            
            # Generate cover image
            print("Generating cover image...")
            cover_path = self.generate_cover_image(game_config)
            if cover_path:
                assets['cover'] = cover_path
                print(f"✓ Cover image generated: {cover_path}")
            else:
                print("✗ Failed to generate cover image")
            
            # Generate role images
            roles = game_config.get('roles', [])
            for role in roles:
                role_name = role.get('name', 'Unknown Role')
                role_desc = role.get('description', 'A mysterious figure')
                
                print(f"Generating image for {role_name}...")
                role_path = self.generate_role_image(
                    role_name, 
                    role_desc, 
                    game_config.get('theme', 'fantasy')
                )
                
                if role_path:
                    # Use consistent naming for assets dictionary
                    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', role_name.lower())
                    assets[f'role_{safe_name}'] = role_path
                    print(f"✓ Role image generated: {role_path}")
                else:
                    print(f"✗ Failed to generate image for {role_name}")
            
        finally:
            os.chdir(original_dir)
        
        return assets


def create_game_config_from_rules(rule_file_path: str) -> Dict:
    """Extract game configuration from a rule file for image generation.
    
    Args:
        rule_file_path: Path to the game rule file
        
    Returns:
        Dictionary containing game configuration for image generation
    """
    config = {
        'title': 'Social Deduction Game',
        'theme': 'fantasy',
        'setting': 'medieval',
        'roles': []
    }
    
    try:
        import importlib.util
        import sys
        
        # Import the rule module using importlib
        spec = importlib.util.spec_from_file_location("rule_module", rule_file_path)
        rule_module = importlib.util.module_from_spec(spec)
        sys.modules["rule_module"] = rule_module
        spec.loader.exec_module(rule_module)
        
        # Extract RULEBOOK dictionary from the module
        if hasattr(rule_module, 'RULEBOOK'):
            rulebook = rule_module.RULEBOOK
            
            # Extract title from module or file name
            filename = os.path.basename(rule_file_path)
            if filename.endswith('.py'):
                config['title'] = filename[:-3].replace('_', ' ').title()
            
            # Extract roles from the role section
            if 'role' in rulebook:
                role_content = rulebook['role']
                
                for role_name, role_description in role_content.items():
                    if role_name and not role_name.lower() in ['init', 'main', 'game', 'player']:
                        # Extract a brief description from the role text
                        description = role_description.strip()
                        config['roles'].append({
                            'name': role_name,
                            'description': description
                        })
            
            # Try to detect theme from common section content
            if 'common' in rulebook:
                content = rulebook['common'].lower()
                if any(word in content for word in ['vampire', 'werewolf', 'witch', 'magic']):
                    config['theme'] = 'dark fantasy'
                    config['setting'] = 'gothic'
                elif any(word in content for word in ['spy', 'agent', 'resistance', 'saboteur']):
                    config['theme'] = 'espionage'
                    config['setting'] = 'modern'
                elif any(word in content for word in ['space', 'alien', 'robot', 'cyber']):
                    config['theme'] = 'sci-fi'
                    config['setting'] = 'futuristic'
                elif any(word in content for word in ['medieval', 'knight', 'castle', 'kingdom']):
                    config['theme'] = 'fantasy'
                    config['setting'] = 'medieval'
        else:
            print(f"Warning: RULEBOOK not found in {rule_file_path}, using fallback method")
            # Fallback to reading file content if RULEBOOK is not available
            with open(rule_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from filename
            filename = os.path.basename(rule_file_path)
            if filename.endswith('.py'):
                config['title'] = filename[:-3].replace('_', ' ').title()
            
            # Look for role definitions in fallback mode
            role_pattern = r'"(\w+)"\s*:\s*"""(.*?)"""'
            roles_found = re.findall(role_pattern, content, re.DOTALL)
            
            for role_name, role_description in roles_found:
                if role_name and not role_name.lower() in ['init', 'main', 'game', 'player']:
                    config['roles'].append({
                        'name': role_name,
                        'description': role_description.strip()[:100] + '...' if len(role_description.strip()) > 100 else role_description.strip()
                    })
    
    except Exception as e:
        print(f"Error importing rule module from {rule_file_path}: {e}")
        # Fallback to original file reading method
        try:
            with open(rule_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = os.path.basename(rule_file_path)
            if filename.endswith('.py'):
                config['title'] = filename[:-3].replace('_', ' ').title()
            
            # Simple fallback role extraction
            role_pattern = r'"(\w+)"\s*:'
            roles_found = re.findall(role_pattern, content)
            
            for role_name in roles_found:
                if role_name and not role_name.lower() in ['init', 'main', 'game', 'player', 'common', 'role', 'gm_guideline', 'system_guideline']:
                    config['roles'].append({
                        'name': role_name,
                        'description': f'A {role_name.lower()} character with mysterious abilities'
                    })
        except Exception as fallback_e:
            print(f"Fallback method also failed: {fallback_e}")
    
    return config


# Example usage
if __name__ == "__main__":
    # Test the image generator
    generator = GameImageGenerator()
    
    # Example game config
    test_config = {
        'title': 'Shadows of Betrayal',
        'theme': 'dark fantasy',
        'setting': 'gothic medieval',
        'roles': [
            {'name': 'Villager', 'description': 'An innocent townsperson trying to survive'},
            {'name': 'Werewolf', 'description': 'A shapeshifter hiding among the villagers'},
            {'name': 'Detective', 'description': 'An investigator seeking the truth'}
        ]
    }
    
    assets = generator.generate_game_assets(test_config)
    print("Generated assets:", assets) 