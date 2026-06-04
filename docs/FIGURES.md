# Figure Capture Plan

Bu dosya rapora girecek ekran goruntulerini planlar. Amac cok fazla gorsel
koymak degil; problemi, ara sonucu ve final sonucu temiz gostermek.

## Rapor icin gerekli screenshotlar

### Figure 1 - Joint input quality

Dosya adi:

```text
report/figures/fig01_joint_input_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off"
```

Beklenen goruntu: Kirmizi skinny/needle triangle'lar belirgin olmali.

### Figure 2 - Instructor reference output

Dosya adi:

```text
report/figures/fig02_joint_instructor_output_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_output.off"
```

Beklenen goruntu: Tamamen veya neredeyse tamamen gri olmali.

### Figure 3 - Our conservative uniform remeshing output

Dosya adi:

```text
report/figures/fig03_joint_uniform_safe_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  outputs/meshes/joint_uniform_safe.off
```

Beklenen goruntu: Input'a gore cok daha az kirmizi/mor triangle kalmali.
Bu ara sonuc raporda "uniform remeshing alone improves quality but does not
fully solve degeneracies" demek icin kullanilacak.

### Figure 4 - Our final adaptive output

Dosya adi:

```text
report/figures/fig04_joint_adaptive_final_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  outputs/meshes/joint_adaptive_final.off
```

Beklenen goruntu: Tamamen gri, bosluksuz ve hocanin output'una benzer olmali.

### Figure 5 - Car4 input quality

Dosya adi:

```text
report/figures/fig05_car4_input_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car4.off"
```

Beklenen goruntu: Cok sayida kirmizi triangle gorunmeli.

### Figure 6 - Car4 cleanup output

Dosya adi:

```text
report/figures/fig06_car4_cleanup_quality.png
```

Komut:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  outputs/meshes/car4_cleanup.off
```

Beklenen goruntu: Buyuk olcude gri olmali. Bir iki kirmizi/mor nokta kalabilir;
bu car4 icin hedeflenen sonuc.

## Opsiyonel screenshotlar

Asagidakiler raporu kalabaliklastirabilir, bu yuzden sadece gerekirse alin:

```text
report/figures/fig07_car1_input_quality.png
report/figures/fig08_car1_cleanup_quality.png
```

Komutlar:

```bash
"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car1.off"

"/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/venv/bin/python" \
  -m meshfix.cli view-quality \
  outputs/meshes/car1_cleanup.off
```

## Screenshot alma notlari

- Mumkunse her joint screenshot'inda modeli benzer acidan tut.
- Polyscope sol panelde renk quantity aktif kalsin.
- Arka plan ve kamera acisi cok onemli degil; onemli olan kirmizi/gri farkinin
  net gorulmesi.
- PNG olarak kaydet.
- Dosyalari `report/figures/` klasorune yukaridaki isimlerle koy.

## Video opsiyonu

Video sart degil. Cok kisa bir video istenirse su akisi yeterli:

1. joint_input ac: kirmizi triangle'lari goster
2. joint_adaptive_final ac: tamamen gri sonucu goster
3. car4 input ac: yogun kirmizi bolgeleri goster
4. car4_cleanup ac: temizlenmis sonucu goster

Konusma gerekmez. Ekranda sadece modellerin donmesi yeterli.

