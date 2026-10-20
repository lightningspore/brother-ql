#!/usr/bin/env python3
"""Generate and digitally verify synthetic QR/Code128 labels; never prints."""
import argparse
import json
from pathlib import Path
import packbits
from PIL import Image, ImageDraw, ImageFont
import qrcode
from barcode.codex import Code128
import zxingcpp
from brother_ql.reader import chunker
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert


def font(size):
    try:
        return ImageFont.truetype('DejaVuSans.ttf',size)
    except OSError:
        return ImageFont.load_default(size=size)


def pattern(model):
    """Use integer pixel modules with explicit quiet zones and no resampling."""
    short='800' if model=='QL-800' else '1110'
    payloads={'QRCode':f'SPOREPRINT-QR-{short}-01', 'Code128':f'SP{short}001'}
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=6,border=4)
    qr.add_data(payloads['QRCode']);qr.make(fit=True)
    qr_image=qr.make_image(fill_color='black',back_color='white').convert('RGB')
    bits=Code128(payloads['Code128']).build()[0]
    module,quiet,height=4,40,120
    bars=Image.new('RGB',(len(bits)*module+2*quiet,height),'white')
    draw=ImageDraw.Draw(bars)
    for i,bit in enumerate(bits):
        if bit=='1':
            draw.rectangle((quiet+i*module,0,quiet+(i+1)*module-1,height-1),fill='black')
    if model=='QL-800':
        image=Image.new('RGB',(991,306),'white')
        draw=ImageDraw.Draw(image)
        draw.text((18,8),'SPOREPRINT BARCODE TEST / NOT POSTAGE',font=font(22),fill='black')
        image.paste(qr_image,(18,55));image.paste(bars,(280,80))
        draw.text((280,215),payloads['Code128'],font=font(24),fill='black')
        draw.text((18,276),payloads['QRCode'],font=font(15),fill='black')
        image=image.transpose(Image.Transpose.ROTATE_90)
    else:
        image=Image.new('RGB',(1164,708),'white')
        draw=ImageDraw.Draw(image)
        draw.text((24,12),'SPOREPRINT BARCODE TEST / NOT POSTAGE',font=font(32),fill='black')
        image.paste(qr_image,(30,85))
        draw.text((280,150),payloads['QRCode'],font=font(28),fill='black')
        image.paste(bars,(30,420))
        draw.text((70,570),payloads['Code128'],font=font(32),fill='black')
    image=image.convert('L').point(lambda value: 255 if value >= 128 else 0,mode='1').convert('RGB')
    return image,payloads


def decoded(image):
    names={zxingcpp.BarcodeFormat.QRCode:'QRCode', zxingcpp.BarcodeFormat.Code128:'Code128'}
    return {names[result.format]:result.text for result in zxingcpp.read_barcodes(image)
            if result.format in names}


def raster_image(data):
    """Reconstruct monochrome transmitted pixels independently of conversion."""
    rows=[];compressed=False
    for command in chunker(data,raise_exception=True):
        if command[:1]==b'M':
            compressed=command[1]==2
        elif command[:2]==b'g\x00':
            rows.append(packbits.decode(command[3:]) if compressed else command[3:])
        elif command[:1] in (b'w',b'G',b'Z'):
            raise ValueError('This verification supports ordinary monochrome QL raster only')
    if not rows or len({len(row) for row in rows})!=1:
        raise ValueError('Missing or inconsistent raster rows')
    pixels=bytes(byte ^ 255 for row in rows for byte in row)
    return Image.frombytes('1',(len(rows[0])*8,len(rows)),pixels).transpose(Image.Transpose.FLIP_LEFT_RIGHT).convert('RGB')


def validate(model,image):
    _,expected=pattern(model)
    before=decoded(image)
    raster=convert(BrotherQLRaster(model),[image],'29x90' if model=='QL-800' else '102',compress=True)
    preview=raster_image(raster)
    after=decoded(preview)
    for fmt,text in expected.items():
        if before.get(fmt)!=text or after.get(fmt)!=text:
            raise ValueError(f'{model}: {fmt} failed source/raster decoding: {before}, {after}')
    return preview,{'model':model,'expected':expected,'source_decoded':before,'raster_decoded':after,'raster_bytes':len(raster)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    reports=[]
    for model in ('QL-800','QL-1110NWB'):
        image,_=pattern(model);preview,report=validate(model,image)
        image.save(args.output/(model+'.png'))
        preview.save(args.output/(model+'-raster.png'))
        reports.append(report)
    (args.output/'verification.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps(reports))


if __name__=='__main__':
    main()
