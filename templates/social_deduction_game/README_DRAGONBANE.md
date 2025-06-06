# Social Deduction Game - Dragonbane Style Template

This template has been enhanced to create game manuals in the style of Dragonbane RPG supplements, complete with automatic image generation for role cards and cover art.

## Features

### Dragonbane-Style Manual Template
- **Atmospheric Design**: Uses colors and styling inspired by the Dragonbane RPG template
- **Multi-Part Structure**: Organized into thematic parts (Welcome, Game Foundation, Characters & Roles, Rules & Gameplay, Strategy & Mastery)
- **Special Boxes**: Three types of styled boxes for highlighting important information:
  - `dragonbox`: For important rules and abilities (red styling)
  - `demonbox`: For optional rules and victory conditions (green styling)  
  - `emptybox`: For designer notes and additional content (outline styling)
- **Two-Column Layout**: Uses `segment` environments for professional magazine-style layout
- **Special List Items**: Enhanced list formatting with `coloritem`, `bolditem`, and `secretitem`

### Role Cards
- **Individual Cards**: Each role gets its own beautifully formatted card
- **Template-Based**: Uses the D&D item card template structure
- **Professional Layout**: Includes role image, objective, abilities, victory conditions, and strategy tips
- **Print-Ready**: Generates individual PDF files for each role card

### AI Image Generation
- **Cover Art**: Automatically generates atmospheric cover images using OpenAI's DALL-E 3
- **Role Images**: Creates unique character art for each role based on descriptions
- **Theme-Aware**: Adapts imagery to match the game's theme and setting

## Setup

### Requirements
Install the required dependencies:
```bash
pip install -r requirements.txt
```

### OpenAI API Key
Set your OpenAI API key as an environment variable:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Generating a Game Manual

1. **Automatic Detection**: The system automatically detects social deduction game templates and uses the Dragonbane format

2. **Run Writeup**: Use the standard command:
```bash
python ai_scientist/perform_writeup.py --folder templates/social_deduction_game/run_X
```

3. **Generated Files**: The process will create:
   - `template.tex` - Main game manual using Dragonbane styling
   - `role_card_*.tex` - Individual role card files
   - `cover_image.png` - Generated cover art
   - `*_card.png` - Role character images
   - `*_manual.pdf` - Final compiled manual
   - `role_card_*.pdf` - Individual role card PDFs

### Manual Image Generation

You can also generate images separately:

```python
from image_generator import GameImageGenerator, create_game_config_from_rules

# Initialize generator
generator = GameImageGenerator()

# Create config from rule file
config = create_game_config_from_rules("your_game_rules.py")

# Generate all assets
assets = generator.generate_game_assets(config, "output_directory")
```

## Template Structure

### Game Manual Sections

1. **Title Page**: Features the game title with cover image
2. **Game Overview**: Dragonbane-style summary box with key game info
3. **Introduction**: Welcome message with atmospheric quote
4. **Game Foundation**: Core mechanics and setup
5. **Characters and Roles**: Detailed role descriptions with ability boxes
6. **Rules and Gameplay**: Complete rules with victory conditions
7. **Strategy and Mastery**: Advanced tips and variants

### Role Card Elements

Each role card includes:
- **Role Name & Type**: Clear identification
- **Character Image**: AI-generated artwork
- **Objective**: What the role is trying to achieve
- **Special Abilities**: Unique powers and when to use them
- **Victory Condition**: How this role wins
- **Strategy Tip**: Helpful advice for playing the role
- **Warnings**: Important notes or restrictions

## Customization

### Colors
The template defines several thematic colors:
- `DragonRed`: Primary accent color for titles and borders
- `DemonGreen`: Secondary color for sections and highlights  
- `ScrollBeige`: Background color for boxes
- `AncientGold`: Used for victory conditions
- `MysticPurple`: Used for abilities
- `ShadowBlack`: Used for strategy tips

### Box Types
- Use `\begin{dragonbox}{Title}` for mandatory rules
- Use `\begin{demonbox}{Title}` for optional rules
- Use `\begin{emptybox}{Title}` for flavor text

### List Items
- `\bolditem{Text}` - Bold list item
- `\coloritem{Text}` - Green bold list item
- `\coloritem[blue]{Text}` - Custom color bold list item
- `\secretitem{Text}` - Red italic bold item for secrets

## Troubleshooting

### Common Issues

1. **Missing Images**: Ensure OpenAI API key is set and you have sufficient credits
2. **Compilation Errors**: Check that all LaTeX packages are installed (`texlive-full` recommended)
3. **Role Card Generation**: Verify that role information exists in the rule files

### Dependencies
- LaTeX distribution (TeXLive or MiKTeX)
- OpenAI Python library
- Internet connection for image generation

## Examples

See the generated files in any completed run directory for examples of:
- Complete game manuals with Dragonbane styling
- Individual role cards with custom artwork
- Professional layout and typography

The template is designed to create publication-quality game manuals that are both functional and visually appealing, suitable for both digital distribution and print production. 