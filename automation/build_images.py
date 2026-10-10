"""Create typography-based sale images; checks every text bounding box."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W,H=1600,1000
NAMES={
 'FE':(['AIを入れる前に','減らす仕事を決める','M365業務削減診断'],'4問診断 ＋ ミニ診断 ＋ 既製パッチ1本','3,000円'),
 'CORE':(['5つの定型業務を','M365×AIで減らす'],'導入順位 ＋ 5パッチ ＋ 導入ガイド','10,000円'),
 'PRO':(['M365×AI','業務削減スターター設計'],'適合診断 ＋ 業務削減マップ ＋ 導入ロードマップ','40,000円')}

def create(tier):
 image=Image.new('RGB',(W,H),'#101f34'); draw=ImageDraw.Draw(image)
 checks=[]
 def text(x,y,value,size,color='#ffffff'):
  font=ImageFont.truetype(FONT,size,index=0)
  box=draw.textbbox((x,y),value,font=font)
  if box[0]<80 or box[1]<60 or box[2]>W-80 or box[3]>H-60:
   raise ValueError(f'{tier}: clipped text: {value}: {box}')
  for old in checks:
   a=old['bbox']
   if box[0]<a[2] and box[2]>a[0] and box[1]<a[3] and box[3]>a[1]:
    raise ValueError(f'{tier}: overlapping text')
  draw.text((x,y),value,font=font,fill=color)
  checks.append({'text':value,'bbox':list(box),'size':size})
 draw.rounded_rectangle((100,90,480,175),radius=18,fill='#b4f1d2')
 text(128,95,'WORK RETIREMENT OS',26,'#101f34')
 text(102,210,'AIを増やさない。仕事を減らす。',42,'#b4f1d2')
 lines,description,price=NAMES[tier]
 y=325
 size=86 if tier!='PRO' else 82
 for line in lines:
  # Adapt the font before drawing if a line is too wide.
  while draw.textbbox((100,y),line,font=ImageFont.truetype(FONT,size,index=0))[2]>W-100:
   size-=2
  text(100,y,line,size)
  y+=122
 text(102,740,description,36,'#d9e2ed')
 text(102,825,price,66)
 text(620,858,'個別開発・設定代行は含みません',30,'#d9e2ed')
 path=ROOT/'media'/f'{tier}.png';path.parent.mkdir(exist_ok=True)
 image.save(path,optimize=True)
 return {'file':f'media/{tier}.png','width':W,'height':H,'checks':checks,'clipping':False,'overlap':False}

if __name__=='__main__':
 results=[create(t) for t in NAMES]
 (ROOT/'qa/image_geometry.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 sheet=Image.new('RGB',(1200,750),'white')
 for i,tier in enumerate(NAMES):
  im=Image.open(ROOT/'media'/f'{tier}.png');im.thumbnail((600,375));sheet.paste(im,((i%2)*600,(i//2)*375))
 sheet.save('/tmp/work_retirement_images.png')
 print('3 PNG images: all text inside margins; no overlapping text')
