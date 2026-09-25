import argparse
import csv
import tempfile
import xml.etree.ElementTree as ET
from src.build_icc_from_bcs import build_profile
from pathlib import Path

def csv_to_bcs(path):
    # Rx report CSV: R,G,B,X,Y,Z; RGB is normally 0-255.
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    required = {'R','G','B','X','Y','Z'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('CSV must contain columns R, G, B, X, Y, Z')
    root = ET.Element('profile')
    for row in rows:
        rgb = [float(row[k]) for k in ('R','G','B')]
        scale = 255.0 if max(rgb) > 1.0 else 1.0
        patch = ET.SubElement(root, 'patch')
        stim = ET.SubElement(patch, 'stimuli')
        for k, value in zip(('red','green','blue'), rgb): ET.SubElement(stim, k).text = str(value / scale)
        result = ET.SubElement(patch, 'results'); xyz = ET.SubElement(result, 'XYZ')
        for k in ('X','Y','Z'): ET.SubElement(xyz, k).text = row[k]
    tmp = tempfile.NamedTemporaryFile(suffix='.bcs', delete=False)
    tmp.close(); ET.ElementTree(root).write(tmp.name, encoding='utf-8', xml_declaration=True)
    return Path(tmp.name)

def ti3_to_bcs(path):
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == 'BEGIN_DATA_FORMAT')
        data_start = next(i for i, line in enumerate(lines) if line.strip() == 'BEGIN_DATA')
    except StopIteration:
        raise ValueError('TI3 is missing data sections')
    fields = lines[start + 1].split(); root = ET.Element('profile')
    for line in lines[data_start + 1:]:
        if not line.strip() or line.strip() == 'END_DATA': continue
        row = dict(zip(fields, line.split()))
        keys = ('RGB_R','RGB_G','RGB_B','XYZ_X','XYZ_Y','XYZ_Z')
        if not all(k in row for k in keys): continue
        rgb = [float(row[k]) for k in keys[:3]]; scale = 100.0 if max(rgb) > 1 else 1.0
        p = ET.SubElement(root,'patch'); s = ET.SubElement(p,'stimuli')
        for k,v in zip(('red','green','blue'),rgb): ET.SubElement(s,k).text=str(v/scale)
        x = ET.SubElement(ET.SubElement(p,'results'),'XYZ')
        for k in keys[3:]: ET.SubElement(x,k[-1]).text=row[k]
    tmp=tempfile.NamedTemporaryFile(suffix='.bcs',delete=False); tmp.close(); ET.ElementTree(root).write(tmp.name,encoding='utf-8',xml_declaration=True); return Path(tmp.name)

def build_device(measurement, raw, out):
    measurement, raw, out = map(Path, (measurement, raw, out))
    temporary = None
    try:
        if measurement.suffix.lower() == '.csv':
            temporary = csv_to_bcs(measurement)
        elif measurement.suffix.lower() == '.ti3':
            temporary = ti3_to_bcs(measurement)
        out.parent.mkdir(parents=True, exist_ok=True)
        build_profile(temporary or measurement, raw, out)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--bcs', required=True)
    ap.add_argument('--raw', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    build_device(args.bcs, args.raw, args.out)
