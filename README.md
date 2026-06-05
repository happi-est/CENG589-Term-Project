# CENG589 Mesh Quality Project

Bu repo, CENG589 Digital Geometry Processing term project icin kuruluyor.
Proje hedefi, verilen OFF mesh modellerindeki skinny/degenerate triangle
problemini olcmek, gorsellestirmek ve remeshing tabanli bir pipeline ile
iyilestirmek.

## Step 1: baseline analysis

Ilk adim sadece analiz yapar; mesh dosyalarini degistirmez.

Ornek:

```bash
python3 -m meshfix.cli analyze \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_output.off" \
  --csv outputs/metrics.csv
```

Bir klasordeki tum OFF dosyalari icin:

```bash
python3 -m meshfix.cli analyze \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars" \
  --csv outputs/car_metrics.csv
```

## Current metrics

- `min angle`: Modeldeki en kucuk ucgen acisi. Cok kucukse skinny triangle vardir.
- `avg min`: Her ucgenin minimum acisinin ortalamasi. Genel kaliteyi ozetler.
- `aspect<.05`: Shortest edge / longest edge orani cok dusuk ucgenler.
- `needle-like`: Cok ince/uzun ucgenler.
- `cap-like`: Maksimum acisi 175 derece uzerinde olan cap tipi ucgenler.
- `bad`: Bu kalite testlerinden en az birine takilan toplam ucgen sayisi.

## Step 2: visualize bad triangles

Bu adimda mesh'i henuz duzeltmiyoruz. Sadece her triangle'i kalite etiketine
gore renklendiriyoruz.

Renkler:

- gri: iyi triangle
- kirmizi: needle, yani cok ince/uzun triangle
- turuncu: shortest-edge / longest-edge orani cok dusuk triangle
- mor: cap, yani bir acisi 175 derece civarinda olan triangle
- siyah: alani neredeyse sifir triangle

Renkli PLY dosyasi uretmek icin:

```bash
python3 -m meshfix.cli colorize \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  --out outputs/figures/joint_input_quality.ply
```

Referans temiz output icin:

```bash
python3 -m meshfix.cli colorize \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_output.off" \
  --out outputs/figures/joint_output_quality.ply
```

Tum araba modelleri icin:

```bash
python3 -m meshfix.cli colorize \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars" \
  --out-dir outputs/figures
```

Polyscope ile interaktif gormek icin, proje klasorundeyken sunu calistir:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off"
```

Beklenen sonuc: `joint_input.off` uzerinde kirmizi bolgeler gormelisin.
Ayni komutu `joint_output.off` ile calistirdiginda model neredeyse tamamen gri
olmali. Bu, hocanin verdigi output'un temiz referans oldugunu gorsel olarak da
dogrular.

## Step 3: uniform remeshing

Bu adim mesh'i ilk kez degistirir. Mantik:

- hedef kenar uzunlugu sec
- hedefin cok ustundeki kenarlari bol
- hedefin cok altindaki kenarlari collapse et
- topology'yi yirtmamak icin operasyonlari konservatif tut

Edge flip ve smoothing opsiyonel/deneysel tutuluyor. Ilk guvenli deneyde
kapali birakiyoruz.

`joint_input.off` icin referans output'un median edge length'i yaklasik `0.044`
oldugu icin ilk deneyde `0.045` kullaniyoruz:

```bash
python3 -m meshfix.cli remesh-uniform \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  --target-length 0.045 \
  --iterations 8 \
  --out outputs/meshes/joint_uniform_safe.off
```

Beklenen ozet:

```text
joint_input.off         bad=258
joint_uniform_safe.off  bad=43
```

Topoloji kontrolu:

```bash
python3 -m meshfix.cli topology \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  outputs/meshes/joint_uniform_safe.off
```

Beklenen ozet: iki mesh icin de `boundary=0` ve `nonmanifold=0`.

Output'u renklendirmek icin:

```bash
python3 -m meshfix.cli colorize \
  outputs/meshes/joint_uniform_safe.off \
  --out outputs/figures/joint_uniform_safe_quality.ply
```

Interaktif gormek icin:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  outputs/meshes/joint_uniform_safe.off
```

Beklenen yorum: Kirmizi ucgen sayisi ciddi azalir, ama tamamen sifirlanmaz.
Bu da bir sonraki adimda degenerate cleanup yapmamiz gerektigini gosterir.

## Step 4: targeted degenerate cleanup

Uniform remeshing sonrasi kalan kotu triangle'lari hedefli temizliyoruz.

Mantik:

- needle triangle: shortest edge collapse
- cap triangle: longest edge split
- her operasyon topology'yi bozmuyorsa uygulanir

Calistir:

```bash
python3 -m meshfix.cli cleanup-degenerate \
  outputs/meshes/joint_uniform_safe.off \
  --iterations 10 \
  --out outputs/meshes/joint_cleanup_targeted_i10.off
```

Beklenen ozet:

```text
joint_uniform_safe.off          bad=43
joint_cleanup_targeted_i10.off  bad=0
```

Topoloji kontrolu:

```bash
python3 -m meshfix.cli topology \
  outputs/meshes/joint_cleanup_targeted_i10.off
```

Beklenen ozet:

```text
boundary=0
nonmanifold=0
```

Renklendir:

```bash
python3 -m meshfix.cli colorize \
  outputs/meshes/joint_cleanup_targeted_i10.off \
  --out outputs/figures/joint_cleanup_targeted_i10_quality.ply
```

Bu PLY dosyasinda model tamamen gri olmali.

## Step 5: adaptive remeshing

Dunyach fikrini burada ekliyoruz: hedef edge length sabit degil, curvature'a gore
degisiyor.

- curvature yuksek bolge: daha kucuk edge
- duz bolge: daha buyuk edge
- amac: daha iyi triangle dagilimi ve daha az gereksiz triangle

Once temiz mesh uzerinde adaptive remesh:

```bash
python3 -m meshfix.cli remesh-adaptive \
  outputs/meshes/joint_cleanup_targeted_i10.off \
  --epsilon 0.002 \
  --min-length 0.025 \
  --max-length 0.075 \
  --iterations 5 \
  --out outputs/meshes/joint_cleanup_adaptive.off
```

Adaptive remesh sonrasi cok az kotu triangle olusabilir. Onlari tekrar temizle:

```bash
python3 -m meshfix.cli cleanup-degenerate \
  outputs/meshes/joint_cleanup_adaptive.off \
  --iterations 5 \
  --out outputs/meshes/joint_adaptive_final.off
```

Beklenen ozet:

```text
joint_cleanup_targeted_i10.off  F=13018  avg min=35.34  bad=0
joint_adaptive_final.off        F=12126  avg min=42.13  bad=0
```

Topoloji kontrolu:

```bash
python3 -m meshfix.cli topology \
  outputs/meshes/joint_adaptive_final.off
```

Beklenen: `boundary=0`, `nonmanifold=0`.

## Step 6: experiment summary and report

Joint, car1 ve car4 deneylerini tek tabloda toplamak icin:

```bash
python3 -m meshfix.cli analyze \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  outputs/meshes/joint_adaptive_final.off \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car1.off" \
  outputs/meshes/car1_cleanup.off \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car4.off" \
  outputs/meshes/car4_cleanup.off \
  --csv outputs/experiment_summary.csv
```

Topoloji kontrolu:

```bash
python3 -m meshfix.cli topology \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/car1_cleanup.off \
  outputs/meshes/car4_cleanup.off
```

Rapor: `report.pdf`
