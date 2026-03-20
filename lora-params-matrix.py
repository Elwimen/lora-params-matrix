#!/usr/bin/python3

import argparse
import matplotlib
import numpy as np
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('--png', action='store_true', help='Save chart as PNG')
parser.add_argument('--svg', action='store_true', help='Save chart as SVG')
parser.add_argument('--show', action='store_true', help='Display chart window')
args = parser.parse_args()

# SX1262 parameters
TX_POWER = 22  # dBm (SX1262 max)
NF = 6  # Noise figure in dB

# SNR requirements by spreading factor
SNR_BY_SF = {
    7: -7.5,
    8: -10.0,
    9: -12.5,
    10: -15.0,
    11: -17.5,
    12: -20.0
}

# Common LoRa bandwidths in Hz
BANDWIDTHS = [7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000, 500000]
BANDWIDTH_LABELS = ['7.8k', '10.4k', '15.6k', '20.8k', '31.25k', '41.7k', '62.5k', '125k', '250k', '500k']

# Spreading factors
SF_RANGE = [7, 8, 9, 10, 11, 12]
SF_LABELS = [f'SF{sf}' for sf in SF_RANGE]

# Coding rate (using 4/5 as default)
CR = 1  # denominator - 4, so 4/5 means CR=1

# LoRaWAN EU868: BW=125kHz, any SF, CR=4/5
LORAWAN_BW = 125000

# MeshCore EU: BW=125kHz, SF=9, CR=4/8
MESHCORE_BW = 125000
MESHCORE_SF = 9

# Meshtastic channel presets: (label, bw_hz, sf, cr_denominator)
# cr_denominator: 5 = CR4/5, 8 = CR4/8
MESHTASTIC_PRESETS = [
    ('LF',  250000, 11, 5),  # Long Fast (default)
    ('LS',  125000, 12, 8),  # Long Slow
    ('LMo', 125000, 11, 8),  # Long Moderate
    ('MF',  250000,  9, 5),  # Medium Fast
    ('MS',  250000, 10, 5),  # Medium Slow
    ('ShF', 250000,  7, 5),  # Short Fast
    ('ShS', 250000,  8, 5),  # Short Slow
    ('ST',  500000,  7, 5),  # Short Turbo
]


def get_markers(bw, sf):
    """Return (cr5_prefix, cr8_prefix, any_marked) for cell annotations."""
    cr5, cr8 = [], []
    if bw == LORAWAN_BW:
        cr5.append('[L]')
    if bw == MESHCORE_BW and sf == MESHCORE_SF:
        cr8.append('[C]')
    for label, pbw, psf, pcr in MESHTASTIC_PRESETS:
        if bw == pbw and sf == psf:
            (cr5 if pcr == 5 else cr8).append(label)
    return ''.join(cr5), ''.join(cr8), bool(cr5 or cr8)


def calc_sensitivity(bw_hz: float, sf: int) -> float:
    """Calculate receiver sensitivity in dBm."""
    snr = SNR_BY_SF[sf]
    return -174 + 10 * np.log10(bw_hz) + NF + snr


def calc_link_budget(bw_hz: float, sf: int) -> float:
    """Calculate link budget in dB."""
    sensitivity = calc_sensitivity(bw_hz, sf)
    return TX_POWER - sensitivity


def calc_bitrate(bw_hz: float, sf: int, cr: int = 1) -> float:
    """Calculate bit rate in bps."""
    return sf * (bw_hz / (2 ** sf)) * (4 / (4 + cr))


def calc_time_on_air(bw_hz: float, sf: int, payload_bytes: int = 10,
                     preamble: int = 8, cr: int = 1, header: bool = True) -> float:
    """Calculate time on air in milliseconds."""
    # Symbol duration
    t_sym = (2 ** sf) / bw_hz * 1000  # ms

    # Preamble duration
    t_preamble = (preamble + 4.25) * t_sym

    # Low data rate optimization (required when symbol time >= 16.38ms)
    de = 1 if (2**sf / bw_hz) >= 0.01638 else 0

    # Header mode
    h = 0 if header else 1

    # Payload symbol count
    num = 8 * payload_bytes - 4 * sf + 28 + 16 - 20 * h
    den = 4 * (sf - 2 * de)
    payload_symbols = 8 + max(np.ceil(num / den) * (cr + 4), 0)

    # Total time on air
    return t_preamble + payload_symbols * t_sym


# Calculate values
link_budget = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))
bitrate_cr5 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))  # CR 4/5
bitrate_cr8 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))  # CR 4/8
toa_1byte_cr5 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))
toa_1byte_cr8 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))
toa_250byte_cr5 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))
toa_250byte_cr8 = np.zeros((len(BANDWIDTHS), len(SF_RANGE)))

for i, bw in enumerate(BANDWIDTHS):
    for j, sf in enumerate(SF_RANGE):
        link_budget[i, j] = calc_link_budget(bw, sf)
        bitrate_cr5[i, j] = calc_bitrate(bw, sf, cr=1)  # CR 4/5
        bitrate_cr8[i, j] = calc_bitrate(bw, sf, cr=4)  # CR 4/8
        toa_1byte_cr5[i, j] = calc_time_on_air(bw, sf, payload_bytes=1, cr=1)
        toa_1byte_cr8[i, j] = calc_time_on_air(bw, sf, payload_bytes=1, cr=4)
        toa_250byte_cr5[i, j] = calc_time_on_air(bw, sf, payload_bytes=250, cr=1)
        toa_250byte_cr8[i, j] = calc_time_on_air(bw, sf, payload_bytes=250, cr=4)

if args.png or args.svg or args.show:
    # Create figure with six heatmaps
    fig, ((ax1, ax2, ax3), (ax4, ax5, ax6)) = plt.subplots(2, 3, figsize=(20, 14))

    # Plot 1: Link Budget Heatmap
    im1 = ax1.imshow(link_budget, cmap='viridis', aspect='auto')
    ax1.set_xticks(range(len(SF_RANGE)))
    ax1.set_xticklabels(SF_LABELS)
    ax1.set_yticks(range(len(BANDWIDTHS)))
    ax1.set_yticklabels(BANDWIDTH_LABELS)
    ax1.set_xlabel('Spreading Factor')
    ax1.set_ylabel('Bandwidth')
    ax1.set_title(f'LoRa Link Budget (SX1262 @ {TX_POWER} dBm)\nHigher = More Range')

    # Add value annotations
    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val = link_budget[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)
            prefix = cr5_pfx + cr8_pfx

            txt = f'{prefix}{val:.0f}'
            weight = 'bold' if marked else 'normal'
            ax1.text(j, i, txt, ha='center', va='center',
                     color='white' if val < 155 else 'black',
                     fontsize=7, fontweight=weight)

    fig.colorbar(im1, ax=ax1, label='Link Budget (dB)')

    # Plot 2: Bit Rate Heatmap (showing both CR 4/5 and CR 4/8)
    im2 = ax2.imshow(np.log10(bitrate_cr5 / 1000), cmap='plasma', aspect='auto')
    ax2.set_xticks(range(len(SF_RANGE)))
    ax2.set_xticklabels(SF_LABELS)
    ax2.set_yticks(range(len(BANDWIDTHS)))
    ax2.set_yticklabels(BANDWIDTH_LABELS)
    ax2.set_xlabel('Spreading Factor')
    ax2.set_ylabel('Bandwidth')
    ax2.set_title('LoRa Bit Rate\nCR 4/5 | CR 4/8')

    def fmt_bps(v):
        if v >= 1000:
            return f'{v/1000:.1f}k'
        return f'{int(v)}'

    # Add value annotations (both CR values)
    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val5 = bitrate_cr5[i, j]
            val8 = bitrate_cr8[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)

            txt = f'{cr5_pfx}CR5:{fmt_bps(val5)}\n{cr8_pfx}CR8:{fmt_bps(val8)}'
            weight = 'bold' if marked else 'normal'
            ax2.text(j, i, txt, ha='center', va='center',
                     color='white' if np.log10(val5/1000) < 1 else 'black',
                     fontsize=6, fontweight=weight)

    cbar2 = fig.colorbar(im2, ax=ax2, label='Bit Rate (log₁₀ kbps)')
    cbar2.set_ticks([-2, -1, 0, 1, 2])
    cbar2.set_ticklabels(['10 bps', '100 bps', '1 kbps', '10 kbps', '100 kbps'])

    # Plot 3: Link Budget × Bit Rate (Figure of Merit)
    fom_cr5 = link_budget * bitrate_cr5
    fom_cr8 = link_budget * bitrate_cr8
    im3 = ax3.imshow(np.log10(fom_cr5), cmap='coolwarm', aspect='auto')
    ax3.set_xticks(range(len(SF_RANGE)))
    ax3.set_xticklabels(SF_LABELS)
    ax3.set_yticks(range(len(BANDWIDTHS)))
    ax3.set_yticklabels(BANDWIDTH_LABELS)
    ax3.set_xlabel('Spreading Factor')
    ax3.set_ylabel('Bandwidth')
    ax3.set_title('Link Budget × Bit Rate\n(Figure of Merit)')

    def fmt_fom(v):
        if v >= 1e6:
            return f'{v/1e6:.1f}M'
        elif v >= 1e3:
            return f'{v/1e3:.0f}k'
        return f'{v:.0f}'

    fom_mid = (np.log10(fom_cr5.min()) + np.log10(fom_cr5.max())) / 2
    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val5 = fom_cr5[i, j]
            val8 = fom_cr8[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)

            txt = f'{cr5_pfx}CR5:{fmt_fom(val5)}\n{cr8_pfx}CR8:{fmt_fom(val8)}'
            weight = 'bold' if marked else 'normal'
            ax3.text(j, i, txt, ha='center', va='center',
                     color='white' if np.log10(val5) < fom_mid else 'black',
                     fontsize=6, fontweight=weight)

    fig.colorbar(im3, ax=ax3, label='Link Budget × Bit Rate (log₁₀)')

    # Plot 4: dB per bps (Range Efficiency)
    bps_per_db_cr5 = bitrate_cr5 / link_budget
    bps_per_db_cr8 = bitrate_cr8 / link_budget

    im4 = ax4.imshow(np.log10(bps_per_db_cr8), cmap='cividis', aspect='auto')
    ax4.set_xticks(range(len(SF_RANGE)))
    ax4.set_xticklabels(SF_LABELS)
    ax4.set_yticks(range(len(BANDWIDTHS)))
    ax4.set_yticklabels(BANDWIDTH_LABELS)
    ax4.set_xlabel('Spreading Factor')
    ax4.set_ylabel('Bandwidth')
    ax4.set_title('Bit Rate/ Link Budget (bps/dB)\nHigher = Throughput per Range')

    db_per_bps_mid = (np.log10(bps_per_db_cr8.min()) + np.log10(bps_per_db_cr8.max())) / 2
    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val5 = bps_per_db_cr5[i, j]
            val8 = bps_per_db_cr8[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)

            txt = f'{cr5_pfx}CR5:{val5:.2f}\n{cr8_pfx}CR8:{val8:.2f}'
            weight = 'bold' if marked else 'normal'
            ax4.text(j, i, txt, ha='center', va='center',
                     color='white' if np.log10(val5) < db_per_bps_mid else 'black',
                     fontsize=6, fontweight=weight)

    fig.colorbar(im4, ax=ax4, label='bps/dB (log₁₀)')

    def fmt_time(v):
        if v >= 1000:
            return f'{v/1000:.1f}s'
        return f'{v:.0f}ms'

    # Plot 5: Time on Air (1-byte payload)
    im5 = ax5.imshow(np.log10(toa_1byte_cr5), cmap='RdYlGn_r', aspect='auto')
    ax5.set_xticks(range(len(SF_RANGE)))
    ax5.set_xticklabels(SF_LABELS)
    ax5.set_yticks(range(len(BANDWIDTHS)))
    ax5.set_yticklabels(BANDWIDTH_LABELS)
    ax5.set_xlabel('Spreading Factor')
    ax5.set_ylabel('Bandwidth')
    ax5.set_title('Time on Air (1-byte payload)\nLower = Better')

    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val5 = toa_1byte_cr5[i, j]
            val8 = toa_1byte_cr8[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)

            txt = f'{cr5_pfx}CR5:{fmt_time(val5)}\n{cr8_pfx}CR8:{fmt_time(val8)}'
            weight = 'bold' if marked else 'normal'
            ax5.text(j, i, txt, ha='center', va='center', color='black',
                     fontsize=6, fontweight=weight)

    fig.colorbar(im5, ax=ax5, label='Time on Air (log₁₀ ms)')

    # Plot 6: Time on Air (250-byte payload)
    im6 = ax6.imshow(np.log10(toa_250byte_cr5), cmap='RdYlGn_r', aspect='auto')
    ax6.set_xticks(range(len(SF_RANGE)))
    ax6.set_xticklabels(SF_LABELS)
    ax6.set_yticks(range(len(BANDWIDTHS)))
    ax6.set_yticklabels(BANDWIDTH_LABELS)
    ax6.set_xlabel('Spreading Factor')
    ax6.set_ylabel('Bandwidth')
    ax6.set_title('Time on Air (250-byte payload)\nLower = Better')

    for i in range(len(BANDWIDTHS)):
        bw = BANDWIDTHS[i]
        for j in range(len(SF_RANGE)):
            sf = SF_RANGE[j]
            val5 = toa_250byte_cr5[i, j]
            val8 = toa_250byte_cr8[i, j]

            cr5_pfx, cr8_pfx, marked = get_markers(bw, sf)

            txt = f'{cr5_pfx}CR5:{fmt_time(val5)}\n{cr8_pfx}CR8:{fmt_time(val8)}'
            weight = 'bold' if marked else 'normal'
            ax6.text(j, i, txt, ha='center', va='center', color='black',
                     fontsize=6, fontweight=weight)

    fig.colorbar(im6, ax=ax6, label='Time on Air (log₁₀ ms)')

    # Add legend for defaults
    legend_line1 = '[L] = LoRaWAN (125kHz, CR4/5)    |    [C] = MeshCore EU (125kHz, SF9, CR4/8)'
    legend_line2 = ('Meshtastic presets — '
                    'LF: Long Fast (250k/SF11/CR5)  '
                    'LS: Long Slow (125k/SF12/CR8)  '
                    'LMo: Long Moderate (125k/SF11/CR8)  '
                    'MF: Med Fast (250k/SF9/CR5)')
    legend_line3 = ('MS: Med Slow (250k/SF10/CR5)  '
                    'ShF: Short Fast (250k/SF7/CR5)  '
                    'ShS: Short Slow (250k/SF8/CR5)  '
                    'ST: Short Turbo (500k/SF7/CR5)')

    fig.text(0.5, 0.055, legend_line1, ha='center', fontsize=8, fontweight='bold')
    fig.text(0.5, 0.033, legend_line2, ha='center', fontsize=8)
    fig.text(0.5, 0.013, legend_line3, ha='center', fontsize=8)

    plt.tight_layout(rect=[0, 0.07, 1, 1])
    if args.png:
        plt.savefig('lora_charts.png', dpi=150)
        print("Saved lora_charts.png")
    if args.svg:
        plt.savefig('lora_charts.svg')
        print("Saved lora_charts.svg")
    if args.show:
        plt.show()

# Print some key values
print("\n=== Link Budget (dB) ===")
print(f"{'BW':<10}", end='')
for sf in SF_RANGE:
    print(f"SF{sf:<6}", end='')
print()
for i, bw in enumerate(BANDWIDTHS):
    print(f"{BANDWIDTH_LABELS[i]:<10}", end='')
    for j in range(len(SF_RANGE)):
        print(f"{link_budget[i,j]:<8.1f}", end='')
    print()

print("\n=== Bit Rate CR5 (bps) ===")
print(f"{'BW':<10}", end='')
for sf in SF_RANGE:
    print(f"SF{sf:<8}", end='')
print()
for i, bw in enumerate(BANDWIDTHS):
    print(f"{BANDWIDTH_LABELS[i]:<10}", end='')
    for j in range(len(SF_RANGE)):
        print(f"{bitrate_cr5[i,j]:<10.0f}", end='')
    print()

print("\n=== Bit Rate CR8 (bps) ===")
print(f"{'BW':<10}", end='')
for sf in SF_RANGE:
    print(f"SF{sf:<8}", end='')
print()
for i, bw in enumerate(BANDWIDTHS):
    print(f"{BANDWIDTH_LABELS[i]:<10}", end='')
    for j in range(len(SF_RANGE)):
        print(f"{bitrate_cr8[i,j]:<10.0f}", end='')
    print()
