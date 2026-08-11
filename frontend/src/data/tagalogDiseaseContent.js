const entry = (description, symptoms, causes, prevention, treatment) => ({
  description,
  symptoms: { visible_signs: symptoms },
  causes: {
    pathogen_type: 'Impeksiyong dulot ng halamang-singaw',
    environmental_factors: causes,
    spread_methods: ['Talsik ng ulan o patubig', 'Kontaminadong kagamitan', 'Pagdikit ng nahawaang bahagi ng halaman'],
  },
  prevention_methods: { farm_sanitation: prevention },
  recommended_treatments: { best_practices: treatment },
})

// These reviewed Filipino descriptions are used whenever the API has no
// translation yet, so changing the Library language never falls back to English.
export const TAGALOG_DISEASE_CONTENT = Object.freeze({
  Anthracnose: entry(
    'Ang antraknosa ay sakit-singaw na nagdudulot ng maitim at lubog na sugat sa tangkay at bunga ng dragon fruit. Mabilis itong lumalala kapag mainit at mahalumigmig ang panahon.',
    ['Maitim at lubog na mga sugat sa tangkay o bunga', 'Lumalaki at nagsasanib ang mga batik', 'Paninilaw at pagkatuyo ng apektadong bahagi'],
    ['Mainit at mahalumigmig na panahon', 'Matagal na pagkabasa ng halaman', 'Mga sugat mula sa pagpuputol o peste'],
    ['Alisin agad ang may sakit na bahagi', 'Linisin at i-disinfect ang mga kagamitan', 'Panatilihing maaliwalas ang pagitan ng mga halaman'],
    ['Putulin at itapon nang maayos ang apektadong bahagi', 'Iwasang diligan ang tangkay at dahon sa gabi', 'Gumamit ng aprubadong fungicide ayon sa label']
  ),
  'Black Spot': entry(
    'Ang Black Spot ay sakit-singaw na lumilikha ng bilog at maitim na batik sa mga tangkay ng dragon fruit. Kapag hindi nagamot, maaaring magsanib ang mga batik at magpahina sa halaman.',
    ['Maliit na bilog na kayumanggi hanggang itim na batik', 'Lumalaki at nagdidikit ang mga batik', 'Humihina o naninilaw ang tangkay'],
    ['Mataas na halumigmig', 'Mahinang sirkulasyon ng hangin', 'Talsik ng tubig mula sa nahawaang halaman'],
    ['Panatilihing malinis ang taniman', 'Iwasan ang sobrang siksik na pagtatanim', 'Regular na suriin ang mga tangkay'],
    ['Putulin ang bahaging maraming batik', 'I-disinfect ang gunting bago lumipat sa ibang halaman', 'Mag-singaw-singaw lamang ayon sa rekomendasyon ng agriculturist']
  ),
  'Brown Spot': entry(
    'Ang Brown Spot ay nagdudulot ng hindi pantay na kayumangging sugat sa tangkay at cladode. Kumakalat ito kapag laging basa o nai-stress ang halaman.',
    ['Hindi pantay na kayumangging batik', 'Tuyong gilid ng sugat', 'Pagdami ng batik sa basang kondisyon'],
    ['Matagal na basa pagkatapos ng ulan', 'Kakulangan sa sustansya', 'Hindi maayos na daloy ng hangin'],
    ['Ayusin ang daluyan ng tubig', 'Magbigay ng balanseng pataba', 'Alisin ang mga nahulog at may sakit na bahagi'],
    ['Alisin ang apektadong bahagi', 'Bawasan ang pagdidilig kapag maulan', 'Maglagay ng naaangkop na fungicide ayon sa label']
  ),
  'Root Rot': entry(
    'Ang Root Rot ay pagkabulok ng ugat na nagiging sanhi ng pagkalanta, mahinang paglaki, at pagbagsak ng halaman. Karaniwan itong dulot ng palaging basang lupa at mahinang drainage.',
    ['Pagkalanta kahit basa ang lupa', 'Mabagal na paglaki', 'Maitim, malambot, o mabahong ugat'],
    ['Nakatigil na tubig sa ugat', 'Mabigat at kulang sa drainage na lupa', 'Sobrang pagdidilig'],
    ['Gumamit ng lupang mabilis mag-drain', 'Huwag magdilig nang sobra', 'Suriin ang ugat bago magtanim'],
    ['Alisin ang bulok na ugat gamit ang malinis na kagamitan', 'Palitan ang sobrang basang lupa', 'Gamutin ang ugat ayon sa payo ng agriculturist']
  ),
  'Soft Rot': entry(
    'Ang Soft Rot ay mabilis na pagkabulok ng tangkay o bunga. Nagiging malambot, basa, at minsan ay mabaho ang apektadong bahagi.',
    ['Malambot at basang bahagi ng tangkay o bunga', 'Mabilis na paglawak ng pagkabulok', 'Maasim o mabahong amoy'],
    ['Sugat sa halaman', 'Mainit at basang panahon', 'Kontaminadong tubig o kagamitan'],
    ['Iwasang masugatan ang halaman', 'Alisin agad ang bulok na bahagi', 'Panatilihing tuyo at malinis ang taniman'],
    ['Putulin ang bulok na bahagi hanggang sa malusog na tisyu', 'Itapon ang nahawaang bahagi malayo sa taniman', 'I-disinfect ang mga kagamitan pagkatapos gamitin']
  ),
  'Stem Rot': entry(
    'Ang Stem Rot ay nagdudulot ng malambot at kupas na sugat sa tangkay na maaaring kumalat at magpabagsak sa apektadong bahagi ng halaman.',
    ['Malambot at maitim o kupas na sugat sa tangkay', 'Pagkatuyo o pagkalanta ng bahagi sa itaas ng sugat', 'Pagkahulog ng apektadong tangkay'],
    ['Sobrang halumigmig', 'Sugatang tangkay', 'Mahinang bentilasyon'],
    ['Panatilihing tuyo ang paligid ng tangkay', 'Magbigay ng sapat na pagitan ng mga halaman', 'Iwasan ang pagpuputol kapag umuulan'],
    ['Putulin ang apektadong tangkay sa malusog na bahagi', 'I-disinfect ang kagamitan bago at pagkatapos magputol', 'Gumamit ng fungicide ayon sa label kung kailangan']
  ),
  'Stem Canker': entry(
    'Ang Stem Canker ay mapanganib na sakit-singaw na nagdudulot ng malalim at maitim na sugat sa tangkay. Maaari nitong hadlangan ang daloy ng tubig at sustansya sa halaman.',
    ['Malalim at maitim na sugat sa tangkay', 'Bitak-bitak o nakaangat na gilid ng sugat', 'Pagkatuyo ng sanga at panghihina ng halaman'],
    ['Mainit at mahalumigmig na kapaligiran', 'Sugatang tangkay mula sa pagpuputol', 'Kontaminadong kagamitan'],
    ['I-disinfect ang kagamitan sa bawat pagputol', 'Alisin agad ang may kanser na tangkay', 'Panatilihing maaliwalas ang taniman'],
    ['Putulin ang may sakit na tangkay hanggang sa malusog na bahagi', 'Itapon nang ligtas ang putol na bahagi', 'Mag-apply ng copper-based fungicide ayon sa label']
  ),
  'Twig Blight': entry(
    'Ang Twig Blight ay nagpapadilim at nagpapatuyo sa dulo ng mga tangkay at bagong tubo. Kapag lumala, bumababa ang sigla at ani ng halaman.',
    ['Panunuyo ng dulo ng tangkay', 'Pagdidilim ng bagong tubo', 'Pag-atras ng pagkatuyo pababa sa tangkay'],
    ['Stress sa panahon', 'Kakulangan sa sustansya', 'Pangalawang impeksiyon sa sugatang bahagi'],
    ['Panatilihing tama ang pagdidilig', 'Magbigay ng balanseng pataba', 'Putulin ang tuyong dulo sa tuyong araw'],
    ['Putulin ang tuyong dulo nang lampas sa apektadong bahagi', 'Linisin ang kagamitan pagkatapos magputol', 'Bantayan ang iba pang tangkay para sa bagong sintomas']
  ),
  'White Spot': entry(
    'Ang White Spot ay nagdudulot ng mapuputi at bilog na batik sa tangkay at bunga ng dragon fruit. Kapag marami ang batik, nababawasan ang kakayahan ng halaman na gumawa ng pagkain.',
    ['Maliit, maputi, at bilog na batik', 'Paninilaw ng tisyu sa paligid ng batik', 'Pagsasanib ng mga batik upang maging mas malaking bahagi'],
    ['Impeksiyong-singaw', 'Hindi balanseng sustansya', 'Stress sa tubig at mahinang sirkulasyon ng hangin'],
    ['Panatilihing maaliwalas ang taniman', 'Magbigay ng balanseng pataba', 'Iwasan ang sobra o kulang na pagdidilig'],
    ['Alisin ang bahaging malubhang apektado', 'Ayusin ang patubig at bentilasyon', 'Gumamit ng sulfur o copper-based fungicide ayon sa label']
  ),
})
