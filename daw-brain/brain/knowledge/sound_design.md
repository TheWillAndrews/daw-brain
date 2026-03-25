# SOUND DESIGN KNOWLEDGE BASE
## For DAW Brain — Synthesis, Patches & Sound Creation

**Comprehensive reference for synthesis fundamentals, Serum 2 patch recipes, Ableton stock instruments, drum sound design, and FX creation.** Tailored for groovy underground tech house at 124–130 BPM on a 2020 Intel MacBook Pro with 8GB RAM, using Ableton Live 12 Suite, Serum 2, LFO Tool, and stock Ableton effects.

Reference artists: YOBBO, CHASEWEST, BELTRAN, SLAMM, CHALANT, Jamie Jones, The Martinez Brothers, Patrick Topping, Solardo

---

## 4.1 SYNTHESIS FUNDAMENTALS

Every synth sound in tech house starts with one of four synthesis methods. Choosing the right one saves CPU and gets you to the sound faster.

### Subtractive (Oscillator → Filter → Amp)
Rich waveform (saw, square) sculpted by filter, shaped by amp envelope. 90% of tech house bass and pads.
- **Best for:** Bass, pads, warm leads, stabs. **Use in:** Serum 2, Analog, Drift
- **Key insight:** The filter envelope IS the character. How aggressively the filter closes after the note triggers defines the "boingy" tech house bass.

### FM Synthesis (Frequency Modulation)
One oscillator modulates another's frequency, creating complex harmonic spectra from simple sines.
- **Best for:** Metallic percussion, bells, glassy plucks, sub bass (pure sine). **Use in:** Operator
- **Key insight:** Non-integer frequency ratios produce inharmonic partials — the shimmer in bells and metallic hits.

### Wavetable Synthesis
Cycles through waveform shapes in a table. Position modulation creates evolving timbres cheaply.
- **Best for:** Evolving textures, morphing pads, complex leads. **Use in:** Serum 2, Wavetable

### Granular Synthesis
Chops audio into tiny grains (1–100ms) and reassembles them. **Use in:** Granulator III (Max for Live).
- **Best for:** Atmospheric pads from vocal samples, glitchy textures, breakdown layers.
- **CPU warning:** Heavy on 8GB RAM. Freeze/bounce immediately. Never run more than one instance.

### Decision Matrix
| Sound Type | First Choice | Second Choice | Avoid |
|---|---|---|---|
| Bass (bouncy/offbeat) | Serum 2 (subtractive) | Drift | Granulator |
| Sub bass | Operator (pure sine) | Serum 2 sub osc | Wavetable |
| Pads | Wavetable | Analog | Operator |
| Pluck stabs | Serum 2 | Wavetable | Granulator |
| Metallic perc | Operator (FM) | Serum 2 noise osc | Analog |
| Evolving textures | Wavetable | Granulator (freeze after) | Operator |
| Acid leads | Serum 2 | Drift | Wavetable |
| Bell/chime | Operator (FM) | Serum 2 | Analog |

---

## 4.2 SERUM 2 DEEP DIVE

Serum 2 is the primary third-party synth for this setup. It is CPU-hungry on 8GB RAM — use it deliberately, freeze tracks when not editing, and prefer Ableton stock instruments for simpler sounds.

### Serum 2 Key Additions (vs Serum 1)
- **3 oscillators** (up from 2) with **dual warp modes** per oscillator (e.g., FM + Sync simultaneously). Disable OSC C when not needed — it's CPU-expensive.
- **10 LFOs** with chaos modes (Lorenz, Rossler) — excellent for Reese bass phasing and evolving textures.
- **Clip Sequencer:** Built-in piano roll stores patterns in presets. Useful for acid sequences baked into the patch.
- **Mod remap curves:** Non-linear modulation shapes on every route. Enables stepped pitch bends and shaped filter sweeps.
- **8 macros** (up from 4), smooth wavetable interpolation, LFO-from-WT function.

### Architecture Overview
- **OSC A:** Primary oscillator. Supports wavetable, classic waveforms, custom imports. Two simultaneous warp modes.
- **OSC B:** Secondary oscillator. Layer with OSC A for thickness or use independently. Two simultaneous warp modes.
- **OSC C (NEW in Serum 2):** Third oscillator. Same capabilities as A and B. Use sparingly on 8GB RAM — disable when not needed.
- **Sub Oscillator:** Pure waveform (sine, triangle, saw, square) one octave below. Direct to output, bypasses filters. Critical for bass patches — provides clean low-end weight.
- **Noise Oscillator:** White/pink/custom noise with independent filter. Essential for risers, texture layers, and transient snap on plucks.

### Filter Types That Matter for Tech House
- **MG Low 24 (Moog-style ladder):** The bass filter. Aggressive, warm resonance that doesn't thin out the low end. Use for all bass patches.
- **SV LP 12 (State Variable Low-Pass 12dB):** Gentler slope for leads and pads. Lets more harmonics through, good for acid-style sounds where you want the filter to sing.
- **SV BP (State Variable Band-Pass):** Isolates a frequency band. Use for filtered vocal textures and mid-range elements.
- **Comb filters:** Creates metallic, resonant tones. Useful for percussion design.

### Envelope Design Principles
**Bass envelopes:** Tight. The filter envelope defines the bounce.
- AMP ENV: Attack 0ms, Decay 0ms, Sustain 100%, Release 80ms
- FILTER ENV (ENV 2): Attack 0ms, Decay 180ms, Sustain 0%, Release 50ms
- The filter envelope amount on cutoff: +40 semitones. This creates the snap-then-close character.

**Pad envelopes:** Slow, evolving. No sudden movements.
- AMP ENV: Attack 120ms, Decay 0ms, Sustain 100%, Release 800ms
- FILTER ENV: Attack 200ms, Decay 2000ms, Sustain 60%, Release 1000ms

**Pluck envelopes:** Instant attack, fast decay, no sustain.
- AMP ENV: Attack 0ms, Decay 200ms, Sustain 0%, Release 100ms
- FILTER ENV: Attack 0ms, Decay 120ms, Sustain 0%, Release 80ms

### LFO Routing for Tech House
- **Filter cutoff modulation for wobble:** LFO 1 → Filter Cutoff, Rate 1/4 synced, Shape: sine, Amount: 20 semitones. Creates a rhythmic filter sweep that locks to tempo.
- **Wavetable position for texture evolution:** LFO 2 → WT Position (OSC A), Rate 2 bars, Shape: sine, Amount: 50%. Slowly morphs the timbre across a phrase.
- **Panning for stereo movement:** LFO 3 → Pan, Rate 1/2, Shape: triangle, Amount: 30%. Keeps leads alive in the stereo field.

### Modulation Matrix Essentials
- **Velocity → Filter Cutoff:** Amount +15 semitones. Harder notes are brighter. Creates dynamic, expressive bass without automation.
- **Velocity → Amp Level:** Amount +6 dB. Harder notes are louder. Standard for any playable patch.
- **Mod Wheel → LFO Amount:** Route mod wheel to control wobble depth. Allows real-time performance control.
- **Aftertouch → Wavetable Position:** For pads — pressing harder morphs the timbre.

### Effects Tab
Use sparingly. Serum's built-in effects eat CPU. Prefer Ableton stock effects on the channel strip — they are lighter and offer better visual feedback.
- **Distortion (Tube mode):** Drive 20%, Mix 40%. Adds warmth to bass without harshness. OK to use in Serum for bass patches.
- **Chorus:** Rate 0.3 Hz, Depth 50%, Mix 30%. Use on pads only. For leads, use Ableton Chorus-Ensemble instead.
- **Reverb/Delay:** Disable in Serum. Use Ableton Reverb and Delay on send channels for shared processing and lower CPU.

### CPU Optimization (Critical for 8GB RAM)
1. **Global quality: "Good"** (not "High" or "Ultra"). Enable "Offline Render at Ultra" for exports.
2. **Disable unused oscillators.** If you only use OSC A and Sub, turn off OSC B and Noise.
3. **Freeze tracks immediately** when you are done editing a Serum patch. Cmd+click the track header → Freeze.
4. **Limit polyphony.** Bass: 1 voice. Leads: 4 voices. Pads: 6 voices. Set in Serum's voice panel.
5. **Avoid Unison above 3 voices.** Each unison voice multiplies CPU. 2x unison at 15 cents detune is enough for width.
6. **Maximum 3 Serum instances** running unfrozen simultaneously. Beyond that, freeze or bounce to audio.
7. **Close the Serum GUI** when not editing. The visual waveform display consumes CPU even when minimized.

### 10 Tech House Patches — Exact Parameter Values

#### Patch 1: Bouncy Offbeat Bass
The signature tech house bass. Played on offbeats (the .3 position of each beat), sidechained to the kick.
- **OSC A:** Basic Shapes wavetable, WT Position 0 (pure saw), no unison
- **OSC B:** OFF
- **Sub:** Sine wave, Level -6 dB (relative to OSC A)
- **Noise:** OFF
- **Filter:** MG Low 24, Cutoff 60 Hz, Resonance 15%, Drive 10%
- **ENV 2 → Filter Cutoff:** +42 semitones, Attack 0ms, Decay 180ms, Sustain 0%, Release 50ms
- **AMP ENV:** Attack 0ms, Decay 0ms, Sustain 100%, Release 80ms
- **Velocity → Filter Cutoff:** +15 semitones
- **Mono ON, Legato ON, Glide: 40ms, Always**
- **Voices:** 1
- **FX:** Distortion (Tube), Drive 18%, Mix 35%
- **Post-Serum chain:** LFO Tool (sidechain to kick, 3–5 dB reduction) → Saturator (Soft Sine, Drive 5 dB) → EQ Eight (HP at 30 Hz, LP at 8 kHz)
- **Play range:** E1–B1 (root notes). Character sits at 80–300 Hz. Sub layer fills 30–80 Hz.

#### Patch 2: Sub Bass Layer
Clean, pure low end. Sits underneath the bouncy bass or stands alone during breakdowns.
- **OSC A:** Basic Shapes, WT Position 50% (sine), no unison
- **OSC B:** OFF
- **Sub:** OFF (OSC A IS the sub)
- **Noise:** OFF
- **Filter:** BYPASS (no filter needed — sine wave has no harmonics to remove)
- **AMP ENV:** Attack 2ms, Decay 0ms, Sustain 100%, Release 60ms
- **Mono ON, Legato ON, Glide: 60ms, Always**
- **Voices:** 1
- **FX:** None in Serum
- **Post-Serum chain:** Utility (mono, -2 dB from character bass) → Limiter (ceiling -1 dB, prevents clicks)
- **Play range:** E1–G1. Never above A1 or the fundamental gets too high for sub duty.

#### Patch 3: Reese Bass
Dark, detuned, phasey bass. Think BELTRAN's murky, twisting low end. Two detuned saws create beating frequencies.
- **OSC A:** Basic Shapes, WT Position 0 (saw), Unison 2 voices, Detune 8 cents
- **OSC B:** Basic Shapes, WT Position 0 (saw), Unison 2 voices, Detune 12 cents, Fine Tune +5 cents from OSC A
- **Sub:** Sine wave, Level -3 dB
- **Noise:** OFF
- **Filter:** MG Low 24, Cutoff 200 Hz, Resonance 0%, Drive 15%
- **ENV 2 → Filter Cutoff:** +20 semitones, Attack 0ms, Decay 400ms, Sustain 30%, Release 200ms
- **AMP ENV:** Attack 0ms, Decay 0ms, Sustain 100%, Release 150ms
- **LFO 1 → Filter Cutoff:** Rate 2 bars, Sine, Amount 18 semitones (slow dark-to-bright sweep)
- **LFO 2 → OSC A WT Position:** Rate 4 bars, Triangle, Amount 10% (subtle timbre drift)
- **Mono ON, Legato ON, Glide: 80ms, Always**
- **Voices:** 1
- **FX:** Distortion (Tube), Drive 25%, Mix 30%
- **Post-Serum chain:** Auto Filter (LP, Cutoff 1.2 kHz, automate over 16 bars for builds) → LFO Tool → EQ Eight (HP 28 Hz)

#### Patch 4: Pluck Stab
Short, punchy chord stab. Used for offbeat rhythmic patterns and one-shot accents.
- **OSC A:** Basic Shapes, WT Position 0 (saw), Unison 4 voices, Detune 18 cents
- **OSC B:** Basic Shapes, WT Position 50% (square), Level -4 dB from OSC A, Unison 2 voices, Detune 10 cents
- **Sub:** OFF
- **Noise:** White noise, Level -18 dB, Filter BP at 4 kHz (adds click transient)
- **Filter:** MG Low 24, Cutoff 80 Hz, Resonance 20%, Drive 5%
- **ENV 2 → Filter Cutoff:** +55 semitones, Attack 0ms, Decay 120ms, Sustain 0%, Release 80ms
- **AMP ENV:** Attack 0ms, Decay 200ms, Sustain 0%, Release 100ms
- **Velocity → Filter Cutoff:** +20 semitones
- **Poly, Voices:** 6
- **FX:** Chorus (Rate 0.2 Hz, Depth 40%, Mix 25%)
- **Post-Serum chain:** Saturator (Soft Sine, Drive 3 dB) → Reverb (send only, Room size 30%, Decay 0.8s, Pre-delay 15ms) → EQ Eight (HP 200 Hz, notch at 400 Hz -3 dB)
- **Play range:** C3–C5. Use minor 7th chords or stacked 5ths.

#### Patch 5: Chord Pad
Warm, evolving background pad. Harmonic context without competing with the groove.
- **OSC A:** Analog wavetable category, WT Position modulated by LFO 2, Unison 3, Detune 20 cents
- **OSC B:** Basic Shapes, WT Position 75%, Level -6 dB, Unison 2, Detune 15 cents
- **Sub/Noise:** OFF / Pink -24 dB
- **Filter:** SV LP 12, Cutoff 2.5 kHz, Res 10%
- **ENV 2 → Cutoff:** +15 semi, A 200ms, D 2000ms, S 60%, R 1000ms
- **AMP ENV:** A 120ms, D 0ms, S 100%, R 800ms
- **LFO 1 → Cutoff:** 4 bars, Sine, 8 semi. **LFO 2 → WT Pos:** 8 bars, Sine, 50%
- **Poly, 6 voices.** Post: Chorus-Ensemble (0.5 Hz, 40%, 30%) → Reverb send (Hall, 2.5s, HP 300 Hz) → Utility (-8 dB, width 130%)
- **Play range:** C3–G4. 2-chord progressions: i–v or i–VII.

#### Patch 6: Acid-Style Lead
303-inspired squelchy lead. Filter resonance is the star — it should sing and scream.
- **OSC A:** Basic Shapes, WT Position 25% (saw-square blend), no unison
- **OSC B:** OFF
- **Sub:** OFF
- **Noise:** OFF
- **Filter:** SV LP 12, Cutoff 300 Hz, Resonance 65%, Drive 25%
- **ENV 2 → Filter Cutoff:** +50 semitones, Attack 0ms, Decay 250ms, Sustain 15%, Release 100ms
- **AMP ENV:** Attack 0ms, Decay 0ms, Sustain 100%, Release 50ms
- **Velocity → Filter Cutoff:** +25 semitones (essential — harder notes scream more)
- **Velocity → ENV 2 Decay:** +100ms (harder notes sustain the filter sweep longer)
- **Mono ON, Legato ON, Glide: 60ms, Always**
- **Voices:** 1
- **FX:** Distortion (Downsample), Drive 15%, Mix 25% — adds grit and digital edge
- **Post-Serum chain:** Saturator (Medium Curve, Drive 8 dB, Dry/Wet 60%) → Auto Filter (LP, Freq 6 kHz, controlled by Envelope, Amount 40%) → Delay (send, 1/8 dotted, Feedback 35%, Dry/Wet 25%)
- **Play range:** C2–C4. Monophonic lines, 16th note patterns with accent variation.

#### Patch 7: Filtered Texture
Atmospheric background — processed until unrecognizable (CHASEWEST aesthetic). Movement and depth, no melodic content.
- **OSC A:** Digital wavetable (any complex table), WT Pos modulated by LFO 1, Unison 2, Detune 25 cents
- **OSC B:** Spectral wavetable, WT Pos offset 50%, Level -3 dB, Unison 2, Detune 30 cents
- **Sub:** OFF. **Noise:** Pink, -15 dB
- **Filter:** SV BP, Center 1.5 kHz, Res 25%, Drive 10%
- **LFO 1 → OSC A WT Pos:** 2 bars, Sine, 80%. **LFO 2 → Filter Freq:** 1 bar, Triangle, 30 semi. **LFO 3 → OSC B WT Pos:** 3 bars, Sine, 60%
- **AMP ENV:** A 50ms, S 100%, R 400ms. **Poly, 4 voices.**
- **Post:** Auto Filter (BP, automate 500 Hz–5 kHz over 8 bars) → Delay (Ping-Pong, 3/16, Fb 45%, 35%) → Reverb send (Hall, 2s) → Utility (-10 dB, width 140%)
- **FREEZE immediately.** Two complex wavetable oscillators + noise is heavy on 8GB RAM.

#### Patch 8: Vocal Formant Synth
Mimics vowel shapes (ah, ee, oh, oo) — organic, human-like quality without vocal samples.
- **OSC A:** Vocal wavetable category ("Vowel"/"Voice" tables), WT Position 0
- **OSC B/Sub/Noise:** ALL OFF
- **Filter:** SV LP 12, Cutoff 4 kHz, Res 30%, Drive 5%
- **LFO 1 → WT Pos:** 1 bar, Sine, 100% (sweeps all vowel shapes per bar — the "talking" effect)
- **ENV 2 → Cutoff:** +20 semi, A 10ms, D 300ms, S 50%, R 200ms
- **AMP ENV:** A 5ms, S 100%, R 200ms. **Mono, Legato, Glide 50ms.**
- **FX:** Chorus (0.4 Hz, 30%, 20%). Post: EQ Eight (+4 dB at 2.5 kHz, HP 150 Hz) → Saturator (Soft Sine, 4 dB) → Reverb send (Room, 0.6s)
- **Play range:** C2–C4. Monophonic lines.

#### Patch 9: White Noise Riser
Tension builder. All oscillators OFF except Noise (white, 0 dB). Filter bypass. AMP ENV: S 100%, R 200ms.
Post: Auto Filter (HP 24, automate 200 Hz → 15 kHz over 8–16 bars, Res 30%) → Utility (automate -20 dB → 0 dB) → Reverb send (increasing wet toward peak).
Trigger one long note 8–16 bars before the drop.

#### Patch 10: Impact / Downlifter
**Impact Hit:** OSC A sine (WT Pos 50%), Pitch ENV +24 semi start, Decay 60ms. Sub sine 0 dB. Noise white -6 dB. Filter MG Low 24, Cutoff 400 Hz. AMP ENV: A 0ms, D 400ms, S 0%, R 200ms. FX: Tube distortion 30%/40%. Post: Compressor (0.1ms, 4:1, -20 dB) → Reverb send (Plate, 1.5s, pre-delay 20ms) → EQ (HP 25 Hz, +3 dB at 60 Hz).

**Downlifter:** Same patch, play C5 with pitch bend descending 2 octaves over 2–4 bars. OR pitch envelope: +24 semi, Decay 3000ms.

---

## 4.3 ABLETON ANALOG

Analog is Ableton's analog-modeling subtractive synth. Two oscillators, two filters, two LFOs. Lighter than Serum on CPU for simple patches. Use it when you need warm, analog character without Serum's wavetable complexity.

### Architecture
Two oscillators (saw/square/sine/noise), two filters (series or parallel), sub oscillator, two LFOs, two envelopes. ~60% of Serum's CPU for comparable patches.

### Tech House Patches
1. **Warm pad:** Both oscs saw, detuned +3/-3 cents. Filter LP 24, cutoff 1.8 kHz, res 15%. LFO 1 → cutoff, 0.1 Hz, 20%. Amp: A 150ms, R 600ms.
2. **Analog bass:** Osc 1 saw, Osc 2 square (PW 60%). Filter LP 24 Ladder, cutoff 200 Hz, res 10%. Env: A 0ms, D 200ms, S 20%, R 80ms. Amount +3000 Hz. Mono, glide 30ms.
3. **Vocoder carrier:** Both oscs saw, stacked fifths (Osc 2: +7 semitones). Route into Vocoder device.

### Stacked Fifths Technique
Osc 1 root (E1), Osc 2 fifth (+7 semi, B1). Play E2 + B2 = stack of E1, B1, E2, B2. Massive, harmonically simple, cuts through. Use for vocoder carriers and wide stab sounds.

---

## 4.4 ABLETON WAVETABLE

Wavetable is Ableton's built-in wavetable synth. Lighter than Serum on CPU, excellent wavetable browser, and integrates natively with Ableton's modulation system.

### Wavetable Browser (Best Categories for Tech House)
- **Basics:** Saw/square/sine transitions. Simple starting points.
- **Complex & Formant:** Vocal textures. Use instead of Serum's vocal tables to save CPU.
- **Harmonics:** Bright, additive textures. Good for pluck stabs.

### Position Modulation
WT Position is the primary sound-shaping tool:
- **LFO:** 1–4 bars for pad evolution, 1/4 for rhythmic timbral changes in leads
- **Envelope:** A 0ms, D 150ms → WT Position for bright-to-dark pluck
- **Velocity:** Harder hits = brighter wavetable frame

### Unison & Detune (CPU Tradeoff)
| Voices | Detune | CPU Impact | Use Case |
|---|---|---|---|
| 1 | 0 | Minimal | Bass, sub, mono leads |
| 2 | 15 cents | Low | Leads needing width |
| 3 | 20 cents | Medium | Pads, chord sounds |
| 5+ | Any | High | Avoid on 8GB RAM |

Rule: Never exceed 3 unison voices in Wavetable on this system. If you need thicker unison, use Serum (which handles unison more efficiently) and freeze.

### Filter Types
- **Clean:** Lowest CPU. Transparent filtering. Use for most patches.
- **OSR (Oversampled Resonance):** Analog-style resonance behavior. Warmer, fuller resonance peak. Use for acid leads and bass where the resonance character matters. 15% more CPU than Clean.
- **MS2:** Modeled after the Korg MS-20 filter. Aggressive, distorted resonance. Use for harsh leads.
- **SMP:** Aggressive character. Good for percussion synthesis.

### Best Uses on 8GB RAM
Default for any non-bass synth sound — 40% less CPU than Serum:
- **Pads:** Complex/Formant category, LFO → WT Position at 4-bar rate
- **Pluck leads:** Harmonics category, envelope → WT Position (fast decay)
- **Simple bass:** Basics (saw), LP filter + envelope — use instead of Serum when Serum's MG Low 24 character isn't needed

---

## 4.5 ABLETON OPERATOR

Operator is Ableton's FM synthesizer with four oscillators (A, B, C, D) arranged in 11 algorithms that define the carrier/modulator routing.

### FM Basics
- **Carrier:** The oscillator you hear. **Modulator:** Reshapes the carrier's timbre (you don't hear it directly).
- **Ratio:** Integer (1:1, 2:1, 3:1) = harmonic overtones. Non-integer (1.41:1, 2.76:1) = metallic, bell-like tones.
- **Modulation amount:** Controlled by modulator's Level. More = brighter/harsher.

### Key Algorithms
- **A (serial D→C→B→A):** Most versatile. Bass and complex metallic tones.
- **B (parallel pairs):** Layered tones — bell + sub in one instance.
- **D (all parallel):** Additive synthesis — build from individual sine harmonics.
- **E (3 mods → 1 carrier):** Maximum harmonic complexity. Metallic percussion.

### Tech House Patches

**FM Sub Bass (Algorithm A):**
- Osc A: Sine, Coarse 1, Level 100%
- Osc B: Sine, Coarse 1, Level 0% (no modulation = pure sine carrier)
- Osc C, D: OFF
- Amp Envelope: Attack 2ms, Decay 0ms, Sustain 100%, Release 50ms
- No filter needed
- Result: The cleanest, lightest sub bass possible. Less CPU than Serum's sub oscillator.

**Metallic Percussion (Algorithm E):**
- Osc A (carrier): Sine, Coarse 1, Level 100%
- Osc B (modulator): Sine, Coarse 3.46 (inharmonic ratio), Level 50%
- Osc C (modulator): Sine, Coarse 7.2 (inharmonic ratio), Level 30%
- Osc D: OFF
- Amp Envelope: Attack 0ms, Decay 180ms, Sustain 0%, Release 100ms
- Osc B Envelope: Attack 0ms, Decay 80ms, Sustain 0%, Release 40ms (modulation decays faster = bright attack, mellow body)
- Result: Bell-like metallic percussion hit. Adjust Osc B/C coarse ratios for different timbres.

**Bell Stab (Algorithm A):**
- Osc A: Sine, Coarse 1, Level 100%
- Osc B: Sine, Coarse 3.0 (3rd harmonic), Level 45%
- Osc C: Sine, Coarse 5.0 (5th harmonic), Level 20%
- Osc D: OFF
- Amp Envelope: Attack 0ms, Decay 600ms, Sustain 0%, Release 300ms
- Osc B Envelope: Attack 0ms, Decay 400ms, Sustain 10%, Release 200ms
- Osc C Envelope: Attack 0ms, Decay 200ms, Sustain 0%, Release 100ms
- Result: Clean bell tone. Higher harmonics decay faster, creating a natural bell-like decay.
- Post-processing: Reverb (Plate, 1.2s, pre-delay 10ms), EQ Eight (HP 300 Hz)

**FM Bass (Punchy, Algorithm A):**
- Osc A: Sine, Coarse 1, Level 100%
- Osc B: Sine, Coarse 1 (same frequency), Level 60%
- Osc B Envelope: Attack 0ms, Decay 100ms, Sustain 0%, Release 40ms
- Amp Envelope: Attack 0ms, Decay 0ms, Sustain 100%, Release 80ms
- Result: The fast-decaying modulation creates a punchy "click" at the note start that settles into a clean sine. Adjust Osc B Level (40–80%) for more or less punch.

**FM Clave / Rimshot (Algorithm E — 3 modulators into 1 carrier):**
- Osc A (carrier): Sine, Coarse 1, Level 100%
- Osc B (modulator): Sine, Coarse 3, Level 80%
- Osc C (modulator): Sine, Coarse 6, Level 40%
- Osc D: OFF
- All Envelopes: Attack 0ms, Decay 30-60ms, Sustain 0%, Release 20ms (very short = percussive click)
- Pitch Envelope on Osc A: +12 semitones, Decay 10ms (creates the sharp "tick" transient)
- Post-processing: EQ Eight (HP 300 Hz, boost at 2-4 kHz +3 dB), short delay (1/16, Feedback 10%, Mix 10%)
- Result: Crisp, tonal percussion hit. Adjust Coarse ratios for different timbres. Higher ratios = more metallic.

**FM Hi-Hat (Algorithm D — all parallel, additive):**
- Osc A: Sine, Coarse 14, Level 100%, Decay 30ms (closed) / 120ms (open)
- Osc B: Sine, Coarse 17, Level 80%, Decay 25ms / 100ms
- Osc C: Sine, Coarse 21, Level 60%, Decay 20ms / 80ms
- Osc D: Sine, Coarse 27, Level 40%, Decay 15ms / 60ms
- All: Attack 0ms, Sustain 0%
- Post-processing: EQ Eight (HP 5 kHz), Saturator (Soft Sine, Drive 3 dB), Utility (Width 120%)
- Result: Metallic, pitched hi-hat with unique character. More distinctive than sample-based hats. Vary Coarse ratios for different hi-hat timbres.

---

## 4.6 ABLETON DRIFT

Drift is Ableton's lightweight analog-modeled synth. Two oscillators with shape morphing, one filter, two LFOs, two envelopes. Uses approximately 30% of the CPU of Analog and 20% of Serum. Included with all editions of Live 11.3+ and Live 12. MPE-compatible.

### Key Features
- Two oscillators: Saw, Pulse (PW), Sine, Saturated. Shape modifiers: Fold, PW, Sync.
- **Drift control:** Analog-style pitch/tone instability. 10–15% for bass, 20–30% for pads, 40%+ for experimental.
- Stereo Spread voice mode. 2 envelopes, 2 LFOs. MPE-compatible.
- **CPU:** Negligible. Run 8–10+ instances on 8GB RAM.

### When to Use Drift
**Use Drift instead of Analog when:**
- You need a quick, warm patch without deep editing
- CPU is tight (multiple synth tracks already running)
- You want analog-style instability (the Drift control)

**Use Analog or Serum instead when:**
- You need dual filters or filter routing options (Analog)
- You need wavetable modulation (Serum 2)
- You need complex modulation routing (Serum 2)

### Tech House Patches

**Drift Bass:**
- Shape: Saw
- Filter: LP 24, Cutoff 150 Hz, Resonance 10%
- Filter Envelope: Amount +4000 Hz, Attack 0ms, Decay 200ms, Sustain 15%, Release 60ms
- Amp Envelope: Attack 0ms, Sustain 100%, Release 70ms
- Mono ON, Glide 35ms
- Post-processing: Saturator (Soft Sine, Drive 6 dB) → LFO Tool → EQ Eight (HP 30 Hz)
- Result: Tight, warm bass. Not as characterful as Serum's MG Low 24 filter, but uses a fraction of the CPU.

**Drift Lead:**
- Shape: Square (pulse width 60%)
- Filter: LP 12, Cutoff 2 kHz, Resonance 35%
- Filter Envelope: Amount +3000 Hz, Attack 0ms, Decay 300ms, Sustain 30%, Release 150ms
- LFO → Filter Cutoff: Rate 1/8 synced, Amount 20%, Shape: Square (creates rhythmic filter stepping)
- Mono ON, Glide 50ms
- Post-processing: Delay (1/8 dotted, Feedback 30%, Dry/Wet 20%) → Reverb (send, Room, 0.5s)

**Drift Pad:**
- Shape: Saw
- Filter: LP 12, Cutoff 3 kHz, Resonance 5%
- Amp Envelope: Attack 200ms, Sustain 100%, Release 1000ms
- LFO → Shape (subtle): Rate 0.08 Hz, Amount 15%
- Drift Amount: 40% (adds analog-style pitch instability and warmth)
- Post-processing: Chorus-Ensemble (Rate 0.3 Hz, Amount 35%, Dry/Wet 25%) → Reverb (send, Hall, 2s decay)
- CPU advantage: You can run 8+ Drift pads simultaneously where you could only run 2–3 Serum pads.

---

## 4.7 DRUM SOUND DESIGN

Tech house drums are sample-based with synthesis layering. Start with quality samples, then layer and process.

### Kick Drum Layering

A tech house kick is three layers combined into one hit:

**Layer 1 — Transient (Click/Snap):**
- Source: Short click sample (wood block, stick hit, or synthesized click from Operator)
- Operator click synthesis: Algorithm D, Osc A sine, Coarse 1, Amp Decay 8ms, Sustain 0%. Pitch envelope: start +36 semitones, Decay 5ms. Result: ultra-short pitch-drop click.
- HP filter at 2 kHz — this layer provides ONLY the attack transient
- Level: -8 dB below body layer

**Layer 2 — Body (Punch):**
- Source: 909-style kick sample OR synthesized
- Operator body synthesis: Algorithm A, Osc A sine, Coarse 1. Pitch envelope: start +12 semitones, Decay 40ms. Amp Decay 150ms, Sustain 0%.
- EQ: BP at 80–200 Hz, cut above 3 kHz
- This is the main kick sound — the fundamental thump

**Layer 3 — Sub (Weight):**
- Source: Pure sine wave tuned to track root note
- Operator sub synthesis: Osc A sine, Coarse 0.5 (one octave down), Level 100%, Amp Decay 200ms
- LP filter at 80 Hz — ONLY sub frequencies
- Level: -6 dB below body layer

**Assembly:**
1. Group all three layers in a Drum Rack or Audio Effect Rack
2. Phase-align: zoom in on waveforms, ensure all three transients hit at the same sample position
3. Apply Glue Compressor on the group: Ratio 4:1, Attack 0.1ms, Release Auto, Threshold to get 3 dB reduction
4. EQ Eight on group: HP at 25 Hz (remove rumble), gentle shelf boost +2 dB at 60 Hz, cut -3 dB at 300 Hz (remove boxiness)

### Tuning Kicks to Your Track
1. Insert Ableton's **Tuner** device on the kick channel
2. Play the kick solo — note the detected fundamental frequency
3. If the kick fundamental clashes with your bass root note (within 2 semitones but not matching), adjust:
   - Transpose the kick sample in Simpler/Sampler to match the track key
   - OR choose a different kick sample
4. The kick's fundamental should either match the bass root note OR sit a perfect fifth/octave away

### Clap/Snare Layering

**Layer 1 — Transient Clap:**
- Source: Crisp, dry clap sample with a sharp transient
- Processing: HP at 500 Hz, Compressor (fast attack 0.5ms, ratio 6:1) to emphasize the crack
- This provides the "snap"

**Layer 2 — Body Snare:**
- Source: Snare sample with weight and tone
- Processing: BP 200–2000 Hz, light saturation (Saturator, Soft Sine, Drive 3 dB)
- This provides the "thud"

**Layer 3 — Reverb Rebound:**
- Source: Same clap sample sent to a dedicated reverb return
- Reverb settings: Room type, Size 25%, Decay 0.4s, Pre-delay 25ms (the pre-delay gap creates the "clap...tap" bounce effect)
- The pre-delay is critical — it separates the initial hit from the reverb tail, creating a distinctive tech house snare bounce

**Assembly:**
- Group layers, Glue Compressor on group: Ratio 2:1, Attack 1ms, Release 100ms
- EQ Eight: HP at 200 Hz, presence boost +2 dB at 3.5 kHz

### Hi-Hat Sound Design

**Method 1 — Filtered Noise:**
- Operator: Osc A noise, LP filter at 12 kHz, Amp Decay 30ms (closed hat) or 150ms (open hat)
- Post-processing: EQ Eight HP at 5 kHz, Transient Shaper (if available) to emphasize attack

**Method 2 — Operator High-Frequency Sine Stack:**
- Algorithm D (all parallel): Osc A sine at Coarse 14, Osc B sine at Coarse 17, Osc C sine at Coarse 21
- Amp Decay: 25ms (closed), 120ms (open)
- Produces a more metallic, pitched hat than noise

**Method 3 — Sample Layering:**
- Layer a bright thin hat (provides rhythm) + a darker hat (provides body)
- Process: HP at 6 kHz, gentle compression, subtle stereo widening with Utility (width 120%)
- Most common approach — start with Splice or Ableton's library hats, layer and process

### Percussion Design & Processing

**Congas/Bongos:** Samples from Ableton's Latin Percussion pack or Splice. EQ: HP 60 Hz, boost +2 dB at 1–2 kHz. Compression: attack 10ms, release 30ms, 3:1. Short reverb send (Room, 400ms, 25%). Pan 20–40% off-center. Pitch envelope in Simpler: +3 semitones, 30ms decay for tonal "pop."

**Rimshots/Claves:** Layer a click transient (2–5 kHz peak) with short sine body (400 Hz, 40ms decay). OR use Operator FM Clave patch (Section 4.5). EQ: HP 300 Hz, boost +3 dB at 2–4 kHz. Short delay send (1/16, Feedback 10%, Mix 15%). Velocity variation 60–110.

**Shakers:** White noise through BP filter (5–10 kHz), 15ms amp decay. OR quality sample. EQ: HP 200 Hz, cut -3 dB at 400–600 Hz. Compression: 1ms attack, 15ms release, 4:1. Level: -12 dB below kick. Alternate velocities (80, 50, 70, 50).

**Percussion Bus Rules:**
- HP every element — save low-end headroom for kick/bass
- Pan percussion across stereo field (never center — that's kick/snare space)
- Velocity variation on everything (static percussion is lifeless)
- Off-grid placement: shift hits 5–15ms early or late for organic feel
- Crush technique: short reverb → heavy compression creates industrial textures (BELTRAN/SLAMM style)
- MPC 16 swing at 54–58% on percussion clips independently
- Group bus: Glue Compressor (2:1, slow attack, auto release, 1–2 dB GR)

---

## 4.8 FX SOUND DESIGN

FX elements signal transitions, build tension, and release energy. They should be functional, not decorative — every FX element serves the arrangement.

### White Noise Risers
**Operator method:** Osc A noise, Level 100%, others OFF. No filter. Post: Auto Filter HP 24 dB/oct, automate 200 Hz → 15 kHz over 8 bars. Utility: automate -18 dB → 0 dB over same period. Optional: Resonance 30% for screaming character. Send to reverb with increasing wet toward peak.

**Variation — Filtered Synth Riser:** Any sustained pad, automate HP 200 Hz → 8 kHz. More musical than pure noise — use in breakdowns.

### Impact Hits
Three layers: (1) Transient — Operator noise burst, 10ms decay. (2) Sub drop — sine with pitch ENV +24 semi, decay 80ms. (3) Reverb tail — send combined to Plate reverb (1.5s, pre-delay 5ms, 50% send).
Group all three, Compressor (fast attack, 4:1). EQ: HP 25 Hz, +3 dB at 60 Hz. Place on beat 1 of every drop.

### Downlifters
**Method 1 — Reverse Riser:** Bounce riser to audio, reverse it. Starts bright/loud, descends to dark/quiet. Place at groove re-entry after breakdown.

**Method 2 — Pitched Noise:** Operator noise, MIDI note spanning 2–4 bars. Pitch bend: +8192 → -8192 linearly. Auto Filter LP: 15 kHz → 500 Hz. Swooping descent.

**Method 3 — Serum:** Patch 10 (Impact/Downlifter), play C5, pitch bend down 2 octaves over 2–4 bars.

### Transition FX

**Reverse Cymbal:** Reverse a crash sample (Rev in Clip view), time peak to land on beat 1 of new section. HP at 1 kHz. Length 1–2 bars.

**Tape Stop:** Automate Simpler Transpose from 0 to -24 semitones over 1 beat. Sounds like a turntable losing power.

**Filter Sweep:** Auto Filter LP on group bus, automate 20 kHz → 500 Hz → 20 kHz over 2–4 bars. "Underwater then surfacing" effect. Once per track max.

**FX Throw:** Last beat before transition, automate send to delay return (0% → 80%), then mute source at section boundary. Delay tail ghosts into next section. Settings: 1/4 note, Feedback 50%, HP 500 Hz, LP 5 kHz.

---

## 4.9 REFERENCE ARTIST SOUND DESIGN TRANSLATION

How to map reference artists to the patches and techniques in this document. Artist biographies and genre context are in `tech_house_production.md`.

### Sound Design Translation Matrix

| Target Artist Vibe | Bass Patch | Synth Approach | Drum Character | FX Density | Reverb |
|---|---|---|---|---|---|
| YOBBO | Bouncy (Patch 1), restrained | Minimal synth, groove-first | Tight, 909-based, percussion-heavy | Minimal | Dry |
| CHASEWEST | Stock Ableton only, Reese-style | Sample processing > synthesis | Tight, 909-based | Minimal | Dry |
| BELTRAN | Reese (Patch 3), aggressive LFO | Serum 2, murky textures | Rolling, reverb-crushed perc | Minimal | Dry |
| SLAMM | Reese + heavier sub layer | Processing-first (CHASEWEST school) | Heavy, bass-weighted | Minimal | Dry |
| Jamie Jones | Analog bass (4.3), warm filter | Warm pads, disco samples | Organic, live Latin perc | Moderate | Medium |
| Martinez Brothers | Analog/Drift bass | Vocal chops, conga/bongo layers | Percussive, Latin layers | Moderate | Medium |
| Patrick Topping | Bouncy (Patch 1, decay 120ms) | Hook-driven riffs, clean mix | Punchy, heavy sidechain | Dramatic | Light |
| Solardo | Bouncy (Patch 1, aggressive) | Bold leads, big hooks | Heavy, festival-ready | Dramatic | Medium |

### Key Emulation Notes
- **BELTRAN bass:** Patch 3 (Reese) + LFO 1 to cutoff at 2–4 bar rate. Process drums through short reverbs then compress heavily.
- **CHASEWEST approach:** Skip Serum entirely. Use Analog/Drift/Wavetable + Auto Filter + Saturator + EQ Eight. The sample IS the sound design.
- **Martinez Brothers percussion:** Section 4.7 conga/bongo processing + layered on top of programmed drums. Vocal chops through delay + saturation.
- **Patrick Topping bass:** Patch 1 with shorter filter ENV 2 decay (120–150ms) and heavier sidechain pumping (5–7 dB).

---

## 4.10 CPU BUDGET GUIDE (8GB RAM Intel Mac)

**Total synth CPU target: 30–40% maximum** — leaves headroom for audio tracks, effects, and DAW overhead.

### CPU Per Synth (Approximate)
- **Operator:** 1–2% per instance. Use for sub bass, percussion synthesis. Can run 5+ unfrozen.
- **Drift:** 2–3% per instance. Use for simple bass/lead/pad. Can run 8+ unfrozen.
- **Wavetable:** 3–5% per instance. Use for pads, leads, textures. Can run 3–4 unfrozen.
- **Analog:** 3–5% per instance. Use for warm pads, analog bass, vocoder carriers. Can run 3–4 unfrozen.
- **Serum 2:** 5–8% per instance. Use for complex bass, wavetable patches. **Max 3 unfrozen.**

### Optimization Rules
1. Freeze Serum 2 tracks when done editing. Close the GUI when not editing.
2. Serum 2 quality: "Good" during production. Oversampling: 2x max (4x is inaudible, doubles CPU).
3. Disable unused Serum 2 oscillators — especially OSC C and dual warp modes.
4. Limit polyphony: bass 1 voice, stabs 4–6, pads 6–8.
5. Use Simpler over Sampler. Consolidate audio clips.
6. Buffer: 256 for recording, 512+ for mixing.

### Synth Selection Decision Tree
```
Wavetable scanning / complex mod / multi-warp? → Serum 2 (freeze after)
Warm analog character, 2 oscillators? → Analog
Simple bass/lead, CPU tight? → Drift
FM percussion / bells / pure sub? → Operator
Evolving pad, moderate CPU? → Wavetable
```
