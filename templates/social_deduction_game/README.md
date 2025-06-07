# Social Deduction Game Template with Nier Automata Styling

This template has been enhanced to create beautiful social deduction game manuals and role cards using **Nier Automata-inspired styling** for the main rulebook and **D&D item card styling** for individual role cards, with **OpenAI DALL-E 3** image generation support.

## Features

### 📖 Nier Automata-Style Game Manual
- **Atmospheric Design**: Dark, mysterious aesthetic inspired by Nier Automata
- **Special Elements**: 
  - `nierbox` for important information
  - `nierquote` for atmospheric quotes
  - `nierquotebox` for highlighted content
  - Custom title page with dramatic styling
- **Professional Layout**: Clean typography with gaming-themed design elements

### 🃏 D&D-Style Role Cards
- **Individual Cards**: Each role gets its own professionally designed card
- **Color-Coded**: Different colors for different alignments (Town/Mafia/Neutral)
- **Complete Information**: Role type, objectives, abilities, victory conditions, strategy tips
- **Print-Ready**: Both PDF and PNG output for easy printing and digital use

### 🎨 AI Image Generation
- **Cover Art**: Automatically generated cover images using OpenAI's DALL-E 3
- **Role Portraits**: Custom character art for each role
- **Thematic Consistency**: Images match the game's theme and atmosphere

## Setup

### Prerequisites
```bash
# LaTeX packages (Ubuntu/Debian)
sudo apt-get install texlive-full

# Python dependencies
pip install openai requests

# Optional: ImageMagick for PNG conversion
sudo apt-get install imagemagick
```

### OpenAI API Key
Set your OpenAI API key for image generation:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

When running the AI Scientist on a social deduction game, the system will automatically:

1. Detect the social deduction game template
2. Generate game manual using Nier Automata styling
3. Create individual role cards using D&D styling
4. Generate AI images for cover and roles
5. Compile everything to PDF

## Template Elements

### Nier Automata Manual Elements
- `nierbox` - Information boxes
- `nierquote` - Atmospheric quotes  
- `nierquotebox` - Highlighted content
- `\nierdiamond` - Decorative diamond symbol

### Role Card Commands
- `\createrolecard{name}{type}{image}{objective}{abilities}{victory}{strategy}{warnings}`
- Color-coded by alignment (Town=Blue, Mafia=Red, Neutral=Orange)

## Testing

Run the test suite:
```bash
cd templates/social_deduction_game
python test_templates.py
```

## Credits

- **Nier Automata Template**: Based on HTsuyoshi's template (GNU aGPL v3)
- **D&D Card Template**: Adapted from D&D 5e item cards
- **Image Generation**: OpenAI DALL-E 3 API 