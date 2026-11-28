# Call of Duty: Black Ops Zombies (T5SP) - Animated Camos

### **[Download](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/)**

**Tested and working on Steam, Plutonium, & the Switch Port ([OpenBLOPS-NX by HDErick](https://github.com/HDErick/OpenBLOPS-NX))**

## How to install

Download one of the layouts below. The zip includes the game folders shown in the steps. If you're installing from this repo, the built files are under `.dist`.

1. Copy `iw_animatedcamos.iwd` into the game's `main` directory. It contains the merged legacy textures and is shared by all three layouts.
2. Choose one map layout below. Back up the installed map patches and copy the ten standard map patches from the chosen folder into `zone\Common`.
3. For the alternate Moon build, copy `zombie_moon_patch_spawn_fix.ff` from the same layout's optional folder. Rename the copy to `zombie_moon_patch.ff` in `zone\Common`.
4. Copy `mod.ff` and `mp_animatedcamos.ff` into `zone\Common`.
5. Copy `patch_ui.ff` into `zone\English` for the animated English front-end TV casings.

| Map layout | Player models and first-person arms |
| --- | --- |
| [With Misty (Normal)](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/download/v3.0/T5-AC-With-Misty-Normal.zip) | Classic Misty for the roster, with static arms and hands |
| [With Misty (Goth)](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/download/v3.0/vT5-AC-With-Misty-Goth.zip) | Misty with static skull-pattern sleeves and gloves |
| [Without Misty](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/download/v3.0/T5-AC-Without-Misty.zip) | Stock player models with an animated camo on the original arms and gloves |

All three map layouts have RGB eye effects for living zombies and animated gun models on purchased wall buys. The front-end TVs use the same animated lightning camo as the M14.

### Optional FOV sliders

[Download FOV Options](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/download/v3.0/T5-AC-FOV-Options.zip). This adds FOV (55-130) and FOV Scale (0.8-2.0) in **Settings > Game** on Steam PC.

Close Black Ops, extract the ZIP, and open PowerShell in the extracted folder. With Python 3.11 or later installed, set `$game` to your install folder and run:

```powershell
$game = 'C:\Program Files (x86)\Steam\steamapps\common\Call of Duty Black Ops'
py -3 .\menu_patch.py install $game
```

The installer backs up the affected game files. Use `restore` in place of `install` to put them back. FOV changes apply during play. The Kino and Der Riese teleporter effects return to the FOV you had before teleporting.

### Optional Texture Options (Steam PC)

[Download Texture Options](https://github.com/Geekmaxxer/T5-Animated-Camos/releases/download/v3.0/T5-AC-Texture-Options.zip) for the FOV sliders and texture switches in **Settings > Game**. **Animated Textures** turns the whole camo pack off, including the Misty swaps. The four switches below it restore their own stock visuals while the pack stays on.

Texture Options includes both FOV sliders. Start with the stock Steam game files and let `setup` install your chosen camo layout too. Close Black Ops, extract Texture Options, and open PowerShell in the extracted folder with Python 3.11 or later installed. Change the paths and choose `normal`, `goth` or `stock` to match your camo ZIP.

```powershell
$game = 'C:\Program Files (x86)\Steam\steamapps\common\Call of Duty Black Ops'
py -3 .\texture_options.py --game $game setup 'C:\Downloads\vT5-AC-With-Misty-Goth.zip' goth
```

If you installed FOV Options separately, run its `restore` command first. If you already installed the camo files by hand, pass `--stock` to `setup` with the path to a clean Steam backup. Add `--moon-fix` to use the alternate Moon patch. If Texture Options already manages your install, run `py -3 .\texture_options.py --game $game update` to keep your current layout, choices and backups.

Launch Black Ops normally through Steam. The background helper starts when you sign in to Windows and applies any texture changes after Black Ops closes. Give it a few seconds before relaunching, or use `play` to apply your choices and launch in one step. Pass `--config` before `setup` or `update` if you use a separate player config. Run `restore` to remove the helper from Windows Startup and restore the game files you had before setup.

## Custom weapons

- Karambit
- Sliquifire

## Animated weapons

- AK74U
- AUG
- Ballistic Knife
- Babygun (31-79 JGb215)
- Bouncing Betty
- Bowie
- China-Lake
- Claymore
- Crossbow
- Commando
- CZ-75
- Dragunov
- FAL
- FAMAS
- G11
- Galil
- Gershes
- HK21
- HS10
- L96A1
- M72 Law
- M14
- M16
- M1911
- Monkey Bombs
- MP5
- MP40
- Olympia
- Python
- Raygun
- RPK
- Scavenger
- Sliquifier
- SPAS
- Spectre
- Stakeout
- STG-44
- Thunder Gun
- Thompson
- Wunderwaffe
- Wavegun
- Left-handed Zapgun
- Right-handed Zapgun
- All PAP variants of each weapon

### New Weapons in this fork

- PM63
- Freeze Gun
- Death Machine
- Arisaka
- BAR
- Double Barrel (long and sawed-off)
- FG42
- Gewehr 43
- Kar98k (including scoped)
- M1 Carbine
- M1 Garand
- Trench Gun
- Type 100
- Sickle
- Bowie
- Sickle/Bowie & Ballistic Knife combinations
- Frag grenade
- Stielhandgranate
- Semtex
- QED
- Matryoshka Dolls
- Spikemore

## Fraga's Extras

- Misty
- Custom fx
- Earth gif
- Removed Tgun lights color overlay
- Removed zombie eye color overlay
- Fixed Japanese version
- Fixed Plutonium version

### New Extras in this fork

- 2 different versions of Misty to choose from
- FOV and FOV Scale slider in Game Options
- Zombie eyes glowing RGB
- George Romero's camera light pole and sunglass frames are now animated
- Trap switches and Mystery Box casings are now animated
- Wall-buy chalk weapon models are now animated on the wall
- Claymores/Spikemores/Bettys are now animated while placed on the ground
- Main menu TVs are now animated
- Animated stock hands and gloves in the Without Misty layout


CO-OP works in testing. This build adds animated materials to more of the gun models you see other players holding. Goth changes the first-person sleeves and gloves, so other players see base Misty in third person.

## Shout out to:

- **_TC_** - For making some animated camos
- **_Badger_** - For making the animated betty
- **_Clippy95_** - For adding misty model

## Made by BoneCrusher, enhanced by Geekmaxxer


[Discord](https://discord.gg/cyHQ8RmBvc) - [YouTube](https://www.youtube.com/channel/UCLspKNozGvrYlb6RCQs6apg) - [Twitch](https://www.twitch.tv/bonecrusher_easy) - [Twitter](https://twitter.com/llBoneCrusherll)

Bone Crusher is the goat so his socials stay
