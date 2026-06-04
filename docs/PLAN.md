# CENG589 Term Project Plan

Bu projeyi kucuk, olculebilir ve raporlanabilir adimlarla ilerletecegiz.
Amacimiz "cok karmasik bir sey yaptik" izlenimi degil; problemin tanimi,
uygulanan yontem, metrikler ve gozlemler arasinda temiz bir bilimsel hat kurmak.

## 1. Mesh quality baseline

Ilk hedefimiz verilen OFF modellerini okuyup kalite sorununu sayilarla gostermek.
Bu adimda hicbir mesh'i degistirmiyoruz.

Olcumler:

- vertex ve face sayisi
- minimum triangle angle
- ortalama minimum triangle angle
- maksimum triangle angle
- shortest-edge / longest-edge aspect ratio
- needle-like triangle sayisi
- cap-like triangle sayisi
- toplam bad triangle sayisi

Bu adimin ciktisi, rapordaki ilk tablo olacak.

## 2. Visualization baseline

Kotu ucgenleri model ustunde renklendirecegiz.
Boylece hocaya sadece tablo degil, gorsel kanit da gosterecegiz.

Beklenen cikti:

- input mesh goruntusu
- bad triangle overlay
- joint_input ve car modellerinden ekran goruntuleri

## 3. Uniform isotropic remeshing

Dunyach makalesinin temel aldigi uniform remeshing hattini kuracagiz:

- long edge split
- short edge collapse
- valence iyilestirmek icin edge flip
- tangential smoothing

Bu adimin amaci mesh kalitesini genel olarak yukseltmek.

## 4. Degenerate cleanup

Slicing1 makalesindeki cap/needle ayrimini projeye ekleyecegiz.
Needle tipi ucgenleri collapse/remesh ile, cap tipi ucgenleri ise daha dikkatli
split/slicing mantigiyla azaltacagiz.

Bu adim rapordaki ana "robust cleanup" bolumu olacak.

## 5. Adaptive remeshing

Dunyach et al. 2013 fikrini ekleyerek hedef edge length'i curvature'a gore
degistirecegiz.

Beklenen davranis:

- duz bolgelerde daha az triangle
- detayli/curvature yuksek bolgelerde daha kucuk triangle
- daha iyi triangle quality / triangle count dengesi

## 6. Experiments and report

Tum modeller icin ayni tabloyu uretecegiz:

- input
- uniform remesh output
- cleanup output
- adaptive output

Raporda solution, results, encountered problems ve interesting observations
basliklarini hocanin proje PDF'indeki beklentiye uygun sekilde dolduracagiz.

