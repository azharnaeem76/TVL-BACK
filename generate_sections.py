"""
Generate comprehensive sections for major Pakistani statutes.
Run: python generate_sections.py
"""
import asyncio
import json
from sqlalchemy import text
from app.core.database import async_session

# Comprehensive sections data for major Pakistani statutes
# statute_name must match DB title exactly
SECTIONS = []

# ═══════════════════════════════════════════════════════════
# PAKISTAN PENAL CODE, 1860 (using both possible names)
# ═══════════════════════════════════════════════════════════
PPC_NAME = "Pakistan Penal Code"
PPC_ALT = "Pakistan Penal Code, 1860"

ppc_sections = [
    # General
    ("1", "Title and Extent", "This Act shall be called the Pakistan Penal Code and extends to the whole of Pakistan.", "یہ ایکٹ تعزیرات پاکستان کہلائے گا اور پورے پاکستان پر لاگو ہوگا۔"),
    ("2", "Punishment of Offences Committed Within Pakistan", "Every person shall be liable to punishment under this Code for every act or omission contrary to the provisions thereof, of which he shall be guilty within Pakistan.", "ہر شخص اس ضابطے کے تحت سزا کا مستحق ہوگا جو پاکستان کے اندر جرم کرے۔"),
    ("6", "Definitions", "Throughout this Code every definition of an offence shall be understood to mean that the offence is committed by a person who voluntarily causes or attempts to cause the relevant harm.", "اس ضابطے میں ہر جرم کی تعریف کا مطلب ہے کہ جرم رضاکارانہ طور پر کیا گیا ہے۔"),
    ("34", "Common Intention", "When a criminal act is done by several persons in furtherance of the common intention of all, each of such persons is liable for that act in the same manner as if it were done by him alone.", "جب مشترکہ ارادے سے مجرمانہ فعل کیا جائے تو ہر شخص اس طرح ذمہ دار ہوگا جیسے اس نے خود کیا ہو۔"),
    ("35", "Similar Intention", "Whenever an act, which is criminal only by reason of its being done with a criminal knowledge or intention, is done by several persons, each of such persons who joins in the act with such knowledge or intention is liable for the act.", "جب جرم صرف مجرمانہ علم یا ارادے سے ہو تو ہر شریک شخص ذمہ دار ہوگا۔"),
    ("53", "Punishments", "The punishments to which offenders are liable under the provisions of this Code are: Death, Imprisonment for life, Imprisonment (rigorous or simple), Forfeiture of property, Fine, Whipping.", "اس ضابطے کے تحت سزائیں: سزائے موت، عمر قید، قید، جائیداد ضبطی، جرمانہ، کوڑے شامل ہیں۔"),
    ("54", "Commutation of Sentence", "The appropriate Government may, without the consent of the offender, commute the sentence of death for any other punishment.", "مناسب حکومت مجرم کی رضامندی کے بغیر سزائے موت کو کسی اور سزا میں تبدیل کر سکتی ہے۔"),
    ("55", "Commutation of Imprisonment for Life", "The appropriate Government may commute the sentence of imprisonment for life for imprisonment of either description for a term not exceeding fourteen years.", "حکومت عمر قید کی سزا کو چودہ سال سے زیادہ نہ ہونے والی قید میں تبدیل کر سکتی ہے۔"),
    ("76", "Act Done by Person Bound by Law", "Nothing is an offence which is done by a person who is bound by law to do it.", "کوئی فعل جرم نہیں ہے جو قانون کے تحت کرنا لازمی ہو۔"),
    ("79", "Act Done by Person Justified by Law", "Nothing is an offence which is done by any person who is justified by law in doing it.", "کوئی فعل جرم نہیں ہے جس کا قانون اجازت دیتا ہو۔"),
    ("80", "Accident in Doing a Lawful Act", "Nothing is an offence which is done by accident or misfortune, and without any criminal intention or knowledge in the doing of a lawful act.", "حادثاتی طور پر جائز فعل کے دوران بغیر مجرمانہ ارادے کے ہونے والا نقصان جرم نہیں ہے۔"),
    ("81", "Act Likely to Cause Harm Done Without Criminal Intent", "Nothing is an offence merely by reason of its being done with the knowledge that it is likely to cause harm, if it be done without any criminal intention to cause harm.", "بغیر مجرمانہ ارادے کے نقصان ہونے کا علم ہونا جرم نہیں ہے۔"),
    ("84", "Act of Person of Unsound Mind", "Nothing is an offence which is done by a person who, at the time of doing it, by reason of unsoundness of mind, is incapable of knowing the nature of the act.", "ذہنی طور پر معذور شخص کا فعل جرم نہیں ہے اگر وہ فعل کی نوعیت سمجھنے سے قاصر ہو۔"),
    ("96", "Right of Private Defence", "Nothing is an offence which is done in the exercise of the right of private defence.", "دفاع ذاتی کے حق میں کیا گیا فعل جرم نہیں ہے۔"),
    ("97", "Right to Defend Body and Property", "Every person has a right to defend his own body and the body of any other person against any offence affecting the human body, and property.", "ہر شخص کو اپنے جسم اور جائیداد کے دفاع کا حق حاصل ہے۔"),
    ("99", "Acts Against Which No Right of Private Defence", "There is no right of private defence against an act which does not reasonably cause the apprehension of death or of grievous hurt.", "ایسے فعل کے خلاف دفاع ذاتی کا حق نہیں ہے جس سے موت یا شدید نقصان کا خدشہ نہ ہو۔"),
    ("100", "When Right Extends to Causing Death", "The right of private defence of the body extends to the voluntary causing of death when there is reasonable apprehension of death, grievous hurt, rape, kidnapping, or acid attack.", "دفاع ذاتی کا حق موت تک پہنچ سکتا ہے جب موت، شدید نقصان، زنا بالجبر، اغوا یا تیزاب حملے کا خدشہ ہو۔"),
    ("107", "Abetment of a Thing", "A person abets the doing of a thing who instigates, engages in conspiracy, or intentionally aids by any act or illegal omission.", "اکسانا، سازش میں شامل ہونا، یا جان بوجھ کر مدد کرنا ابھارنا کہلاتا ہے۔"),
    ("109", "Punishment of Abetment", "Whoever abets any offence shall, if the act abetted is committed in consequence of the abetment, be punished with the punishment provided for the offence.", "جو شخص کسی جرم کی ترغیب دے وہ اسی سزا کا مستحق ہوگا جو اصل جرم کے لیے مقرر ہے۔"),
    ("120A", "Criminal Conspiracy", "When two or more persons agree to do, or cause to be done an illegal act, or an act which is not illegal by illegal means, such an agreement is designated a criminal conspiracy.", "جب دو یا زیادہ افراد غیر قانونی فعل کرنے پر متفق ہوں تو یہ مجرمانہ سازش ہے۔"),
    ("120B", "Punishment of Criminal Conspiracy", "Whoever is a party to a criminal conspiracy to commit an offence punishable with death or imprisonment for life shall be punished.", "مجرمانہ سازش میں شریک ہر شخص سزا کا مستحق ہوگا۔"),
    ("141", "Unlawful Assembly", "An assembly of five or more persons is designated an unlawful assembly if the common object is to commit any offence.", "پانچ یا زیادہ افراد کا اجتماع غیر قانونی اجتماع ہے اگر مقصد جرم کرنا ہو۔"),
    ("143", "Punishment for Unlawful Assembly", "Whoever is a member of an unlawful assembly shall be punished with imprisonment up to six months, or with fine, or with both.", "غیر قانونی اجتماع کے رکن کو چھ ماہ قید یا جرمانہ یا دونوں سزا ہو سکتی ہے۔"),
    ("147", "Rioting", "Whenever force or violence is used by an unlawful assembly, or by any member thereof, every member of such assembly is guilty of the offence of rioting.", "جب غیر قانونی اجتماع طاقت استعمال کرے تو ہر رکن فساد کا مجرم ہے۔"),
    ("148", "Rioting Armed with Deadly Weapon", "Whoever is guilty of rioting, being armed with a deadly weapon or with anything which, used as a weapon of offence, is likely to cause death, shall be punished with imprisonment up to three years.", "ہتھیار سے لیس فسادی تین سال تک قید کا مستحق ہے۔"),
    ("153A", "Promoting Enmity Between Groups", "Whoever promotes or attempts to promote feelings of enmity or hatred between different classes of citizens shall be punished.", "مختلف طبقات میں نفرت پھیلانے والا سزا کا مستحق ہوگا۔"),
    ("191", "Giving False Evidence", "Whoever, being legally bound by an oath to state the truth, makes any statement which is false and which he either knows or believes to be false, gives false evidence.", "جو شخص حلف کے بعد جھوٹا بیان دے وہ جھوٹی گواہی دیتا ہے۔"),
    ("193", "Punishment for False Evidence", "Whoever intentionally gives false evidence in any stage of a judicial proceeding shall be punished with imprisonment which may extend to seven years and shall also be liable to fine.", "عدالتی کارروائی میں جان بوجھ کر جھوٹی گواہی دینے والے کو سات سال قید اور جرمانہ ہو سکتا ہے۔"),
    ("295", "Injuring Place of Worship", "Whoever destroys, damages or defiles any place of worship, or any object held sacred by any class of persons with the intention of thereby insulting the religion.", "عبادت گاہ کو نقصان پہنچانا یا بے حرمتی کرنا جرم ہے۔"),
    ("295A", "Deliberate Act to Outrage Religious Feelings", "Whoever, with deliberate and malicious intention of outraging the religious feelings of any class, insults the religion or religious beliefs of that class.", "کسی مذہب کی جان بوجھ کر توہین کرنا جرم ہے۔"),
    ("295B", "Defiling the Holy Quran", "Whoever wilfully defiles, damages or desecrates a copy of the Holy Quran shall be punishable with imprisonment for life.", "قرآن پاک کی بے حرمتی عمر قید کی سزا ہے۔"),
    ("295C", "Use of Derogatory Remarks about the Holy Prophet", "Whoever by words, either spoken or written, or by visible representation, or by any imputation, innuendo, or insinuation directly or indirectly defiles the sacred name of the Holy Prophet Muhammad (PBUH) shall be punished with death.", "نبی کریم صلی اللہ علیہ وسلم کی شان میں گستاخی سزائے موت ہے۔"),
    ("298", "Uttering Words to Wound Religious Feelings", "Whoever, with the deliberate intention of wounding the religious feelings of any person, utters any word or makes any sound shall be punished.", "کسی کے مذہبی جذبات مجروح کرنے والا سزا کا مستحق ہوگا۔"),
    ("298A", "Use of Derogatory Remarks Against Holy Personages", "Whoever by words, either spoken or written, directly or indirectly, defiles the sacred name of any wife, family member, or companion of the Holy Prophet shall be punished with imprisonment up to three years.", "ازواج مطہرات یا صحابہ کرام کی شان میں گستاخی تین سال قید کی سزا ہے۔"),
    ("299", "Definitions in Chapter of Qatl", "In this Chapter: (a) offence of qatl means causing death of a person (b) qatl-e-amd means intentional killing (c) qatl-e-khata means unintentional killing.", "قتل کے باب میں: قتل عمد یعنی جان بوجھ کر قتل، قتل خطا یعنی غیر ارادی قتل۔"),
    ("300", "Qatl-e-Amd (Intentional Murder)", "Whoever, with the intention of causing death or with the intention of causing bodily injury to a person sufficient in ordinary course of nature to cause death, causes the death of such person, commits qatl-e-amd.", "جو شخص ارادتاً کسی کو قتل کرے وہ قتل عمد کا مرتکب ہے۔"),
    ("301", "Qatl-e-Amd Not Proved", "If it is not proved that the offender had intention to cause death or bodily injury sufficient to cause death, but death is caused, the offence shall be qatl and not qatl-e-amd.", "اگر قتل عمد ثابت نہ ہو تو جرم قتل ہوگا نہ کہ قتل عمد۔"),
    ("302", "Punishment of Qatl-e-Amd", "Whoever commits qatl-e-amd shall, subject to the provisions of this Chapter, be punished with death as qisas, or imprisonment for life as ta'zir, or imprisonment up to twenty-five years as ta'zir.", "قتل عمد کی سزا: قصاص میں موت، یا تعزیری عمر قید، یا پچیس سال قید۔"),
    ("304", "Qatl-i-Khata (Unintentional Killing)", "Whoever, without intent to kill, causes death by a rash or negligent act not amounting to qatl-e-amd commits qatl-i-khata.", "جو بغیر ارادے کے لاپرواہی سے کسی کو ہلاک کرے وہ قتل خطا کا مرتکب ہے۔"),
    ("305", "Punishment of Qatl-i-Khata", "Whoever commits qatl-i-khata shall be liable to diyat and may also be punished with imprisonment up to ten years as ta'zir.", "قتل خطا کی سزا دیت اور دس سال تک تعزیری قید ہے۔"),
    ("308", "Proof of Qatl-e-Amd", "Qatl-e-amd shall be proved in any of the following ways: (a) confession (b) evidence as provided in Article 17 of the Qanun-e-Shahadat Order.", "قتل عمد ان طریقوں سے ثابت ہوگا: اقرار جرم، یا قانون شہادت کے مطابق شہادت۔"),
    ("309", "Qatl-e-Amd Not Liable to Qisas", "Qatl-e-amd shall not be liable to qisas in certain cases, including when the offender is a minor or insane, or when the right of qisas is waived.", "بعض صورتوں میں قصاص لازم نہیں ہوتا، جیسے نابالغ یا پاگل کی صورت میں۔"),
    ("310", "Waiver or Compounding of Qisas", "The wali (heirs of the victim) may at any time waive the right of qisas, in which case the court shall pass such order as it may deem fit.", "ولی (مقتول کے وارثین) کسی بھی وقت قصاص کا حق معاف کر سکتے ہیں۔"),
    ("311", "Ta'zir After Waiver of Qisas", "Where qisas is not applicable or has been waived, the court may award ta'zir having regard to the facts and circumstances of the case.", "قصاص معاف ہونے کے بعد عدالت حالات کے مطابق تعزیری سزا دے سکتی ہے۔"),
    ("312", "Punishment for Qatl During Fasad-fil-Arz", "Whoever commits qatl-e-amd in the name or on the pretext of honour, or commits qatl in fasad-fil-arz, shall be punished with death or imprisonment for life.", "غیرت کے نام پر قتل یا فساد فی الارض میں قتل کی سزا موت یا عمر قید ہے۔"),
    ("316", "Diyat (Blood Money)", "The court shall fix the value of diyat which shall not be less than the value of thirty thousand six hundred and thirty grams of silver.", "دیت کی رقم تیس ہزار چھ سو تیس گرام چاندی کی قیمت سے کم نہیں ہوگی۔"),
    ("319", "Hurt", "Whoever causes bodily pain, disease or infirmity to any person is said to cause hurt.", "جو شخص کسی کو جسمانی تکلیف، بیماری یا کمزوری پہنچائے وہ ایذا رسانی کرتا ہے۔"),
    ("320", "Qatl-e-Amd Liable to Qisas", "Qatl-e-amd is liable to qisas subject to the conditions of this Chapter.", "قتل عمد قصاص کے تابع ہے اس باب کی شرائط کے مطابق۔"),
    ("322", "Qatl-bis-Sabab", "Whoever, without any intention to cause death of, or cause harm to, any person, does any unlawful act which becomes a cause of death, is said to commit qatl-bis-sabab.", "جو بغیر ارادے کے غیر قانونی فعل سے کسی کی موت کا سبب بنے وہ قتل بالسبب کا مرتکب ہے۔"),
    ("324", "Attempt to Commit Qatl-e-Amd", "Whoever does any act with such intention or knowledge and under such circumstances that, if he by that act caused death, he would be guilty of qatl-e-amd, shall be punished with imprisonment up to ten years.", "قتل عمد کی کوشش کی سزا دس سال تک قید ہے۔"),
    ("332", "Hurt by Rash or Negligent Act", "Whoever causes hurt to any person by doing any act so rashly or negligently as to endanger human life or personal safety, shall be punished.", "لاپرواہی سے ایذا رسانی کی سزا ہے۔"),
    ("337A", "Shajjah (Injuries to the Head or Face)", "Whoever causes shajjah (injury to the head or face) shall be liable to punishment. Types include shajjah-i-khafifah, shajjah-i-mudihah, shajjah-i-hashimah, shajjah-i-munaqqilah, and shajjah-i-ammah.", "سر یا چہرے پر زخم لگانے والا سزا کا مستحق ہوگا۔ اس میں خفیفہ، موضحہ، ہاشمہ، منقلہ اور آمہ شامل ہیں۔"),
    ("337F", "Jurh (Injuries Other Than to Head/Face)", "Whoever causes jurh (injury to any part of body other than head or face) shall be punished. Includes jaifah (body cavity penetrating wound) and ghayr-jaifah (non-penetrating wound).", "سر و چہرے کے علاوہ جسم پر زخم لگانے کی سزا ہے۔ جائفہ اور غیر جائفہ شامل ہیں۔"),
    ("337H", "Punishment of Hurt Caused by Corrosive Substance", "Whoever causes hurt by means of corrosive substance (acid) shall be punished with imprisonment for life or up to fourteen years.", "تیزاب سے نقصان پہنچانے والے کو عمر قید یا چودہ سال قید کی سزا ہے۔"),
    ("337L", "Itlaf-i-Udw (Destruction of Organ)", "Whoever destroys or permanently impairs the functioning of an organ or faculty of a person is said to cause itlaf-i-udw.", "کسی شخص کے عضو کو تباہ کرنا یا مستقل طور پر ناکارہ بنانا اتلاف عضو ہے۔"),
    ("337N", "Punishment for Arsh", "Arsh shall be payable for specified injuries as compensation determined by the court based on the nature and extent of the injury.", "ارش مخصوص زخموں کے لیے معاوضہ ہے جو عدالت زخم کی نوعیت کے مطابق مقرر کرے گی۔"),
    ("354", "Assault or Criminal Force to Woman with Intent to Outrage Modesty", "Whoever assaults or uses criminal force to any woman, intending to outrage or knowing it to be likely to outrage her modesty, shall be punished with imprisonment up to two years.", "عورت کی عصمت دری کی نیت سے حملہ کرنے والے کو دو سال قید کی سزا ہے۔"),
    ("354A", "Assault or Use of Criminal Force to Woman and Stripping", "Whoever assaults or uses criminal force to any woman and strips her of her clothes, shall be punished with death or imprisonment for life.", "عورت کے کپڑے اتارنے کی سزا موت یا عمر قید ہے۔"),
    ("363", "Kidnapping", "Whoever kidnaps any person from Pakistan or from lawful guardianship is said to commit kidnapping.", "پاکستان سے یا قانونی سرپرستی سے اغوا کرنا اغوا ہے۔"),
    ("364A", "Kidnapping for Ransom", "Whoever kidnaps any person in order that such person may be detained for ransom shall be punished with death or imprisonment for life.", "تاوان کے لیے اغوا کرنے کی سزا موت یا عمر قید ہے۔"),
    ("365", "Kidnapping with Intent to Wrongfully Confine", "Whoever kidnaps any person with intent to wrongfully confine that person shall be punished with imprisonment up to seven years.", "ناجائز قید کے لیے اغوا کرنے کی سزا سات سال تک قید ہے۔"),
    ("375", "Rape", "A man is said to commit rape who has sexual intercourse with a woman: against her will, without her consent, with her consent obtained by fear of death or hurt, when she is unable to communicate consent, or when she is under sixteen years of age.", "مرد زنا بالجبر کا مرتکب ہے جب عورت کی مرضی کے خلاف یا رضامندی کے بغیر ہمبستری کرے۔"),
    ("376", "Punishment of Rape", "Whoever commits rape shall be punished with death or imprisonment for a term not less than ten years and not more than twenty-five years and shall also be liable to fine.", "زنا بالجبر کی سزا موت یا دس سے پچیس سال قید اور جرمانہ ہے۔"),
    ("377", "Unnatural Offences", "Whoever voluntarily has carnal intercourse against the order of nature with any man, woman or animal shall be punished with imprisonment for life or imprisonment up to ten years.", "غیر فطری جرم کی سزا عمر قید یا دس سال تک قید ہے۔"),
    ("378", "Theft", "Whoever, intending to take dishonestly any moveable property out of the possession of any person without that person's consent, moves that property, is said to commit theft.", "کسی شخص کی ملکیت کی منقولہ جائیداد بغیر رضامندی بے ایمانی سے لینا چوری ہے۔"),
    ("379", "Punishment for Theft", "Whoever commits theft shall be punished with imprisonment up to three years, or with fine, or with both.", "چوری کی سزا تین سال تک قید یا جرمانہ یا دونوں ہے۔"),
    ("380", "Theft in Dwelling House", "Whoever commits theft in any building used as a human dwelling shall be punished with imprisonment up to seven years.", "رہائشی مکان میں چوری کی سزا سات سال تک قید ہے۔"),
    ("382", "Theft After Preparation for Causing Death or Hurt", "Whoever commits theft, having made preparation for causing death, hurt, or restraint, shall be punished with rigorous imprisonment up to ten years.", "قتل یا ایذا رسانی کی تیاری سے چوری کی سزا دس سال تک سخت قید ہے۔"),
    ("383", "Extortion", "Whoever intentionally puts any person in fear of any injury to that person, or to any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property, commits extortion.", "ڈرا دھمکا کر جائیداد حاصل کرنا بھتہ خوری ہے۔"),
    ("384", "Punishment for Extortion", "Whoever commits extortion shall be punished with imprisonment up to three years, or with fine, or with both.", "بھتہ خوری کی سزا تین سال تک قید یا جرمانہ یا دونوں ہے۔"),
    ("390", "Robbery", "In all robbery there is either theft or extortion. When theft is robbery: theft is robbery if, in order to committing of the theft, the offender causes or attempts to cause death, hurt, or wrongful restraint.", "ڈکیتی میں چوری یا بھتہ خوری شامل ہے۔ جب چوری کے دوران قتل، ایذا یا ناجائز قید ہو تو یہ ڈکیتی ہے۔"),
    ("392", "Punishment for Robbery", "Whoever commits robbery shall be punished with rigorous imprisonment up to ten years and shall also be liable to fine.", "ڈکیتی کی سزا دس سال تک سخت قید اور جرمانہ ہے۔"),
    ("395", "Dacoity", "When five or more persons conjointly commit or attempt to commit a robbery, every person so committing, attempting or aiding, is said to commit dacoity.", "پانچ یا زیادہ افراد مل کر ڈکیتی کریں تو ڈاکہ ہے۔"),
    ("396", "Dacoity with Murder", "If any one of five or more persons, who are conjointly committing dacoity, commits murder, every one of those persons shall be punished with death or imprisonment for life.", "ڈاکے کے دوران قتل ہو تو ہر شریک کو موت یا عمر قید کی سزا ہے۔"),
    ("397", "Robbery with Attempt to Cause Death or Grievous Hurt", "If at the time of committing robbery, the offender uses any deadly weapon, or causes grievous hurt, the imprisonment shall not be less than seven years.", "ڈکیتی میں مہلک ہتھیار استعمال ہو تو سزا سات سال سے کم نہیں ہوگی۔"),
    ("406", "Criminal Breach of Trust", "Whoever, being entrusted with property, dishonestly misappropriates or converts to his own use that property, commits criminal breach of trust.", "امانت میں خیانت کرنا مجرمانہ خیانت ہے۔"),
    ("408", "Criminal Breach of Trust by Clerk or Servant", "Whoever, being a clerk or servant, commits criminal breach of trust, shall be punished with imprisonment up to seven years.", "ملازم کی امانت میں خیانت کی سزا سات سال تک قید ہے۔"),
    ("409", "Criminal Breach of Trust by Public Servant", "Whoever, being a public servant, commits criminal breach of trust, shall be punished with imprisonment for life or imprisonment up to ten years.", "سرکاری ملازم کی خیانت کی سزا عمر قید یا دس سال قید ہے۔"),
    ("415", "Cheating", "Whoever, by deceiving any person, fraudulently induces the person so deceived to deliver any property, or to consent that any person shall retain any property, commits cheating.", "دھوکہ دہی سے جائیداد حاصل کرنا فراڈ ہے۔"),
    ("420", "Cheating and Dishonestly Inducing Delivery of Property", "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property shall be punished with imprisonment up to seven years.", "فراڈ سے جائیداد حاصل کرنے کی سزا سات سال تک قید ہے۔"),
    ("463", "Forgery", "Whoever makes any false document or part of a document with intent to cause damage or injury, or to support any claim or title, commits forgery.", "جعلی دستاویز بنانا جعل سازی ہے۔"),
    ("468", "Forgery for Purpose of Cheating", "Whoever commits forgery, intending that the document forged shall be used for the purpose of cheating, shall be punished with imprisonment up to seven years.", "دھوکہ دہی کے لیے جعل سازی کی سزا سات سال تک قید ہے۔"),
    ("471", "Using Forged Document as Genuine", "Whoever fraudulently uses as genuine any document which he knows to be forged shall be punished.", "جعلی دستاویز کو اصلی کے طور پر استعمال کرنا جرم ہے۔"),
    ("489F", "Dishonour of Cheque", "Whoever dishonestly issues a cheque which is dishonoured on presentation shall be punished with imprisonment up to three years, or with fine, or with both.", "جان بوجھ کر بے اثر چیک جاری کرنے کی سزا تین سال قید یا جرمانہ یا دونوں ہے۔"),
    ("493", "Cohabitation Caused by Deceitfully Inducing Belief of Lawful Marriage", "Whoever by deceit causes any woman to believe that she is lawfully married to him and cohabits with her, shall be punished.", "دھوکے سے شادی کا یقین دلا کر ہمبستری کرنا جرم ہے۔"),
    ("496", "Marriage Ceremony Gone Through Without Lawful Marriage", "Whoever goes through the ceremony of marriage knowing that thereby no lawful marriage is effected commits an offence.", "جائز شادی کے بغیر شادی کی رسم ادا کرنا جرم ہے۔"),
    ("497", "Adultery (Repealed)", "This section has been repealed. Previously dealt with the offence of adultery.", "یہ دفعہ منسوخ ہو چکی ہے۔"),
    ("498", "Enticing or Taking Away a Married Woman", "Whoever takes or entices away any woman who is married, with intent to have illicit intercourse, shall be punished.", "شادی شدہ عورت کو بہکانا جرم ہے۔"),
    ("499", "Defamation", "Whoever, by words either spoken or intended to be read, or by signs or by visible representations, makes or publishes any imputation concerning any person, intending to harm the reputation of such person, is said to defame that person.", "کسی شخص کی عزت کو نقصان پہنچانے کے ارادے سے الزام لگانا ہتک عزت ہے۔"),
    ("500", "Punishment for Defamation", "Whoever defames another shall be punished with simple imprisonment up to two years, or with fine, or with both.", "ہتک عزت کی سزا دو سال تک سادہ قید یا جرمانہ یا دونوں ہے۔"),
    ("503", "Criminal Intimidation", "Whoever threatens another with any injury to his person, reputation or property with intent to cause alarm, commits criminal intimidation.", "کسی کو نقصان کی دھمکی دینا مجرمانہ دھمکی ہے۔"),
    ("506", "Punishment for Criminal Intimidation", "Whoever commits the offence of criminal intimidation shall be punished with imprisonment up to two years, or with fine, or with both. If threat is to cause death or grievous hurt, up to seven years.", "مجرمانہ دھمکی کی سزا دو سال قید، موت کی دھمکی ہو تو سات سال تک۔"),
    ("509", "Word, Gesture or Act Intended to Insult Modesty of Woman", "Whoever, intending to insult the modesty of any woman, utters any word, makes any sound or gesture, shall be punished.", "عورت کی حیا کے خلاف الفاظ یا اشارے کرنا جرم ہے۔"),
    ("510", "Misconduct in Public by Drunken Person", "Whoever, in a state of intoxication, appears in any public place and causes annoyance to any person, shall be punished.", "نشے میں عوامی جگہ پر بدتمیزی کرنا جرم ہے۔"),
    ("511", "Punishment for Attempting to Commit Offences", "Whoever attempts to commit an offence punishable with imprisonment and in such attempt does any act towards the commission of the offence, shall be punished.", "قابل سزا جرم کی کوشش کرنا بھی سزا کا مستحق ہے۔"),
]

# ═══════════════════════════════════════════════════════════
# CODE OF CRIMINAL PROCEDURE, 1898
# ═══════════════════════════════════════════════════════════
CRPC_NAME = "Code of Criminal Procedure"
CRPC_ALT = "Code of Criminal Procedure, 1898"

crpc_sections = [
    ("4", "Trial of Offences Under Penal Code", "All offences under the Pakistan Penal Code shall be investigated, inquired into, tried, and otherwise dealt with according to the provisions of this Code.", "تعزیرات پاکستان کے تمام جرائم کی تحقیقات اور مقدمات اس ضابطے کے مطابق ہوں گی۔"),
    ("22", "Local Jurisdiction of Courts", "Every offence shall ordinarily be inquired into and tried by a Court within the local limits of whose jurisdiction it was committed.", "ہر جرم عام طور پر اس علاقے کی عدالت میں سنا جائے گا جہاں جرم ہوا۔"),
    ("46", "How Arrest is Made", "In making an arrest the police officer shall actually touch or confine the body of the person to be arrested.", "گرفتاری کرتے وقت پولیس افسر مجرم کے جسم کو چھوئے گا یا قابو میں کرے گا۔"),
    ("54", "Arrest Without Warrant", "Any police officer may, without an order from a Magistrate and without a warrant, arrest any person who has been concerned in any cognizable offence.", "پولیس قابل دست اندازی جرم میں بغیر وارنٹ گرفتار کر سکتی ہے۔"),
    ("55", "Arrest of Vagabonds", "Any police officer may arrest without a warrant any person found taking precautions to conceal his presence under circumstances suggesting commission of a cognizable offence.", "مشتبہ شخص کو بغیر وارنٹ گرفتار کیا جا سکتا ہے۔"),
    ("61", "Person Arrested Not to be Detained More Than 24 Hours", "No police officer shall detain in custody a person arrested without warrant for a longer period than under all the circumstances of the case is reasonable, and such period shall not exceed twenty-four hours.", "بغیر وارنٹ گرفتار شخص کو چوبیس گھنٹے سے زیادہ حراست میں نہیں رکھا جا سکتا۔"),
    ("154", "Information in Cognizable Cases (FIR)", "Every information relating to the commission of a cognizable offence, if given orally to an officer in charge of a police station, shall be reduced to writing and signed by the informant. A copy shall be given to the informant forthwith.", "قابل دست اندازی جرم کی اطلاع تھانہ مقرر کو دی جائے گی جو تحریر کر کے مخبر کو نقل دے گا۔ یہ ایف آئی آر ہے۔"),
    ("155", "Information in Non-Cognizable Cases", "When information is given to an officer in charge of a police station of a non-cognizable offence, he shall enter the substance thereof in a book and refer the informant to the Magistrate.", "ناقابل دست اندازی جرم کی اطلاع پر پولیس ریکارڈ کرے گی اور مخبر کو مجسٹریٹ کے پاس بھیجے گی۔"),
    ("156", "Police Officer's Power to Investigate Cognizable Cases", "Any officer in charge of a police station may, without the order of a Magistrate, investigate any cognizable case which a Court having jurisdiction over the local area would have power to inquire into.", "تھانہ مقرر مجسٹریٹ کے حکم کے بغیر قابل دست اندازی مقدمے کی تحقیقات کر سکتا ہے۔"),
    ("157", "Procedure for Investigation", "If from information received or otherwise an officer in charge of a police station has reason to suspect the commission of a cognizable offence, he shall send a report to a Magistrate.", "تحقیقات کے دوران پولیس مجسٹریٹ کو رپورٹ بھیجے گی۔"),
    ("161", "Examination of Witnesses by Police", "Any police officer making an investigation may examine orally any person supposed to be acquainted with the facts and circumstances of the case.", "تحقیقاتی پولیس افسر مقدمے سے واقف کسی بھی شخص سے زبانی پوچھ گچھ کر سکتا ہے۔"),
    ("164", "Recording of Confessions and Statements", "Any Magistrate may record any confession or statement made to him in the course of an investigation or at any time afterwards before the commencement of the inquiry or trial.", "مجسٹریٹ تحقیقات کے دوران اعتراف جرم یا بیان ریکارڈ کر سکتا ہے۔"),
    ("173", "Report of Police Officer on Investigation", "Every investigation shall be completed without unnecessary delay and the officer in charge shall forward a report (challan) to the Magistrate empowered to take cognizance.", "تحقیقات مکمل ہونے پر پولیس مجسٹریٹ کو چالان (رپورٹ) بھیجے گی۔"),
    ("190", "Cognizance of Offences by Magistrates", "Any Magistrate of the first class may take cognizance of any offence upon receiving a complaint, a police report (challan), or information from any person.", "درجہ اول کا مجسٹریٹ شکایت، پولیس رپورٹ، یا اطلاع پر جرم کا نوٹس لے سکتا ہے۔"),
    ("200", "Examination of Complainant", "A Magistrate taking cognizance of an offence on complaint shall examine upon oath the complainant.", "شکایت پر نوٹس لینے والا مجسٹریٹ شکایت کنندہ کو حلف پر بیان دلوائے گا۔"),
    ("202", "Postponement of Issue of Process", "Any Magistrate, on receipt of a complaint, may postpone the issue of process and either inquire into the case himself or direct an investigation to be made by a police officer.", "مجسٹریٹ شکایت ملنے پر خود تحقیقات کر سکتا ہے یا پولیس کو حکم دے سکتا ہے۔"),
    ("204", "Issue of Process", "If the Magistrate is of opinion that there is sufficient ground for proceeding, he shall issue process.", "اگر مجسٹریٹ کو کافی بنیاد نظر آئے تو وہ سمن یا وارنٹ جاری کرے گا۔"),
    ("241A", "Summary Trial", "In trials before Magistrates of certain offences, the Magistrate may try the case summarily.", "بعض جرائم میں مجسٹریٹ مختصر مقدمے کی سماعت کر سکتا ہے۔"),
    ("249A", "Acquittal", "If in any case the Magistrate finds that the charge against an accused is groundless, the accused shall be acquitted.", "اگر مجسٹریٹ الزام بے بنیاد پائے تو ملزم بری ہوگا۔"),
    ("265", "Judgment", "The judgment in every trial in any Criminal Court shall be pronounced by the presiding officer in open Court.", "ہر فوجداری عدالت کا فیصلہ کھلی عدالت میں سنایا جائے گا۔"),
    ("345", "Compounding of Offences", "The offences punishable under the sections of the Pakistan Penal Code specified in the table may be compounded by the persons mentioned in the table.", "مخصوص جرائم کی صلح متاثرہ فریق کی رضامندی سے ہو سکتی ہے۔"),
    ("397", "Appeal from Sentence", "An appeal shall lie to the Court of Session from any sentence passed by a Magistrate.", "مجسٹریٹ کی سزا کے خلاف سیشن عدالت میں اپیل ہو سکتی ہے۔"),
    ("401", "High Court's Powers of Revision", "The High Court may call for and examine the record of any proceeding before any Criminal Court for the purpose of satisfying itself as to the correctness of any finding.", "ہائی کورٹ کسی بھی فوجداری عدالت کے ریکارڈ کا جائزہ لے سکتی ہے۔"),
    ("426", "Suspension of Sentence Pending Appeal", "Pending an appeal by a convicted person, the Appellate Court may order that the execution of the sentence be suspended.", "اپیل کے دوران سزا کا نفاذ معطل کیا جا سکتا ہے۔"),
    ("435", "Power of Revision", "The High Court or any Sessions Judge may call for and examine the record of any proceeding before any inferior Criminal Court.", "ہائی کورٹ یا سیشن جج کسی بھی زیریں عدالت کے ریکارڈ کا جائزہ لے سکتا ہے۔"),
    ("439", "High Court's Power to Direct Further Inquiry", "In revision, the High Court may direct further inquiry or order a fresh trial.", "نظرثانی میں ہائی کورٹ مزید تحقیقات یا نئے مقدمے کا حکم دے سکتی ہے۔"),
    ("491", "Power of High Court to Issue Directions (Habeas Corpus)", "The High Court may direct that a person within the limits of its jurisdiction detained in any custody be set at liberty if there is no sufficient ground for such detention.", "ہائی کورٹ ناجائز حراست سے رہائی کا حکم دے سکتی ہے (ہیبیس کارپس)۔"),
    ("497", "When Bail May be Taken in Case of Non-Bailable Offence", "When any person accused of a non-bailable offence is arrested, he may be released on bail if the Court considers that there are reasonable grounds for believing that he is not guilty.", "ناقابل ضمانت جرم میں عدالت ضمانت دے سکتی ہے اگر بے گناہی کے معقول اسباب ہوں۔"),
    ("498", "Bail in Non-Bailable Offence Before High Court", "The High Court or Court of Sessions may direct that any person accused of a non-bailable offence be released on bail.", "ہائی کورٹ یا سیشن کورٹ ناقابل ضمانت جرم میں ضمانت دے سکتی ہے۔"),
    ("540", "Power to Summon Material Witness", "Any Court may, at any stage of any inquiry, trial or other proceeding, summon any person as a witness, or recall and re-examine any person already examined.", "عدالت کسی بھی مرحلے پر کسی کو گواہ کے طور پر بلا سکتی ہے۔"),
    ("561A", "Inherent Powers of High Court", "Nothing in this Code shall be deemed to limit or affect the inherent power of the High Court to make such orders as may be necessary to prevent abuse of the process of any Court.", "ہائی کورٹ کو عدالتی عمل کے غلط استعمال کو روکنے کے لیے موروثی اختیارات حاصل ہیں۔"),
]

# ═══════════════════════════════════════════════════════════
# CONSTITUTION OF PAKISTAN, 1973
# ═══════════════════════════════════════════════════════════
CONST_NAME = "Constitution of Pakistan 1973"

const_sections = [
    ("1", "The Republic and Its Territories", "Pakistan shall be a Federal Republic to be known as the Islamic Republic of Pakistan. The territories shall comprise the provinces of Balochistan, KPK, Punjab, Sindh, Islamabad Capital Territory.", "پاکستان ایک وفاقی جمہوریہ ہوگا جو اسلامی جمہوریہ پاکستان کے نام سے جانا جائے گا۔"),
    ("2", "Islam as State Religion", "Islam shall be the State religion of Pakistan.", "اسلام پاکستان کا سرکاری مذہب ہوگا۔"),
    ("2A", "The Objectives Resolution", "The principles and provisions set out in the Objectives Resolution are hereby made substantive part of the Constitution.", "قرارداد مقاصد آئین کا لازمی حصہ ہے۔"),
    ("4", "Right of Individuals to be Dealt with in Accordance with Law", "No action detrimental to the life, liberty, body, reputation or property of any person shall be taken except in accordance with law.", "کسی شخص کی جان، آزادی، عزت یا جائیداد کے خلاف کارروائی قانون کے مطابق ہی ہوگی۔"),
    ("8", "Laws Inconsistent with Fundamental Rights to be Void", "Any law, or any custom or usage having the force of law, inconsistent with fundamental rights shall be void.", "بنیادی حقوق کے خلاف قانون کالعدم ہوگا۔"),
    ("9", "Security of Person", "No person shall be deprived of life or liberty save in accordance with law.", "کسی شخص کو قانون کے مطابق کے علاوہ جان یا آزادی سے محروم نہیں کیا جائے گا۔"),
    ("10", "Safeguards as to Arrest and Detention", "No person who is arrested shall be detained in custody without being informed of the grounds for such arrest, nor shall he be denied the right to consult and be defended by a legal practitioner.", "گرفتار شخص کو وجوہات بتائی جائیں گی اور وکیل سے مشورے کا حق ہوگا۔"),
    ("10A", "Right to Fair Trial", "For the determination of his civil rights and obligations or in any criminal charge against him, a person shall be entitled to a fair trial and due process.", "ہر شخص کو منصفانہ مقدمے اور مناسب قانونی عمل کا حق ہے۔"),
    ("11", "Slavery and Forced Labour Prohibited", "Slavery is non-existent and forbidden and no law shall permit or facilitate its introduction in any form. All forms of forced labour and traffic in human beings are prohibited.", "غلامی، جبری مشقت اور انسانی تجارت ممنوع ہے۔"),
    ("14", "Inviolability of Dignity of Man", "The dignity of man and the privacy of home shall be inviolable.", "انسان کی عزت اور گھر کی رازداری ناقابل تسخیر ہے۔"),
    ("15", "Freedom of Movement", "Every citizen shall have the right to remain in, and, subject to any reasonable restriction imposed by law, enter and move freely throughout Pakistan.", "ہر شہری کو پاکستان میں آزادانہ نقل و حرکت کا حق ہے۔"),
    ("16", "Freedom of Assembly", "Every citizen shall have the right to assemble peacefully and without arms, subject to any reasonable restrictions imposed by law.", "ہر شہری کو پرامن اجتماع کا حق ہے۔"),
    ("17", "Freedom of Association", "Every citizen shall have the right to form associations or unions, subject to any reasonable restrictions imposed by law.", "ہر شہری کو تنظیمیں بنانے کا حق ہے۔"),
    ("18", "Freedom of Trade, Business or Profession", "Subject to qualifications prescribed by law, every citizen shall have the right to enter upon any lawful profession or occupation.", "ہر شہری کو جائز پیشہ اختیار کرنے کا حق ہے۔"),
    ("19", "Freedom of Speech", "Every citizen shall have the right to freedom of speech and expression, and there shall be freedom of the press, subject to any reasonable restrictions imposed by law.", "ہر شہری کو آزادی اظہار اور آزادی صحافت کا حق ہے۔"),
    ("19A", "Right to Information", "Every citizen shall have the right to have access to information in all matters of public importance subject to regulation and reasonable restrictions imposed by law.", "ہر شہری کو عوامی اہمیت کے معاملات میں معلومات تک رسائی کا حق ہے۔"),
    ("20", "Freedom to Profess Religion", "Every citizen shall have the right to profess, practice and propagate his religion, subject to law, public order and morality.", "ہر شہری کو مذہب کی آزادی کا حق ہے۔"),
    ("22", "Safeguards as to Educational Institutions in Respect of Religion", "No person attending any educational institution shall be required to receive religious instruction other than his own religion.", "تعلیمی ادارے میں اپنے مذہب کے علاوہ مذہبی تعلیم مجبور نہیں۔"),
    ("23", "Provision as to Property", "Every citizen shall have the right to acquire, hold and dispose of property in any part of Pakistan, subject to the Constitution and any reasonable restrictions imposed by law.", "ہر شہری کو جائیداد رکھنے اور فروخت کرنے کا حق ہے۔"),
    ("25", "Equality of Citizens", "All citizens are equal before law and are entitled to equal protection of law. There shall be no discrimination on the basis of sex alone.", "تمام شہری قانون کے سامنے برابر ہیں۔ صنف کی بنیاد پر امتیاز نہیں ہوگا۔"),
    ("25A", "Right to Education", "The State shall provide free and compulsory education to all children of the age of five to sixteen years.", "ریاست پانچ سے سولہ سال کے تمام بچوں کو مفت اور لازمی تعلیم فراہم کرے گی۔"),
    ("175", "Establishment and Jurisdiction of Courts", "There shall be a Supreme Court of Pakistan, a High Court for each Province, and such other courts as may be established by law.", "پاکستان کی سپریم کورٹ، ہر صوبے کے لیے ہائی کورٹ اور دیگر عدالتیں قائم ہوں گی۔"),
    ("184", "Original Jurisdiction of Supreme Court", "The Supreme Court shall have original jurisdiction in any dispute between two or more Governments. Under clause (3), the Supreme Court may take up matters of public importance involving fundamental rights.", "سپریم کورٹ حکومتوں کے درمیان تنازعات اور بنیادی حقوق کے اہم معاملات میں اصل دائرہ اختیار رکھتی ہے۔"),
    ("185", "Appellate Jurisdiction of Supreme Court", "The Supreme Court shall have appellate jurisdiction from judgments, decrees, final orders or sentences of a High Court.", "سپریم کورٹ کو ہائی کورٹ کے فیصلوں کے خلاف اپیل سننے کا اختیار ہے۔"),
    ("186", "Advisory Jurisdiction", "If the President considers that it is desirable to obtain the opinion of the Supreme Court on any question of law, he may refer the question to the Supreme Court for consideration.", "صدر قانونی سوال پر سپریم کورٹ سے رائے لے سکتا ہے۔"),
    ("187", "Issue and Execution of Processes of Supreme Court", "The Supreme Court shall have power to issue such directions, orders or decrees as may be necessary for doing complete justice.", "سپریم کورٹ مکمل انصاف کے لیے ضروری احکامات جاری کر سکتی ہے۔"),
    ("199", "Jurisdiction of High Court (Writ Jurisdiction)", "Each High Court may, on the application of any aggrieved person, issue directions including writs of habeas corpus, mandamus, prohibition, quo warranto and certiorari.", "ہائی کورٹ متاثرہ شخص کی درخواست پر ہیبیس کارپس، مینڈیمس، پروہیبیشن، کوو وارنٹو اور سرشیاری کے رٹ جاری کر سکتی ہے۔"),
    ("203", "Federal Shariat Court", "There shall be constituted a Federal Shariat Court consisting of not more than eight Muslim Judges to examine and decide whether any law is repugnant to the injunctions of Islam.", "وفاقی شرعی عدالت یہ فیصلہ کرے گی کہ آیا کوئی قانون اسلامی احکام کے خلاف ہے۔"),
    ("212", "Administrative Courts and Tribunals", "Notwithstanding anything herein contained, the appropriate Legislature may by Act provide for the establishment of one or more Administrative Courts or Tribunals.", "مناسب مقننہ انتظامی عدالتیں قائم کر سکتی ہے۔"),
    ("227", "Provisions Relating to the Holy Quran and Sunnah", "All existing laws shall be brought in conformity with the Injunctions of Islam as laid down in the Holy Quran and Sunnah.", "تمام موجود قوانین قرآن و سنت کے مطابق بنائے جائیں گے۔"),
    ("232", "Proclamation of Emergency", "If the President is satisfied that a grave emergency exists in which the security of Pakistan is threatened by war or external aggression or by internal disturbance, he may issue a Proclamation of Emergency.", "صدر ہنگامی حالت کا اعلان کر سکتا ہے اگر پاکستان کی سلامتی کو خطرہ ہو۔"),
    ("245", "Functions of Armed Forces", "The Armed Forces shall defend Pakistan against external aggression or threat of war, and subject to law, act in aid of civil power when called upon to do so.", "مسلح افواج بیرونی جارحیت کے خلاف دفاع کریں گی اور شہری حکومت کی مدد کریں گی۔"),
]

# ═══════════════════════════════════════════════════════════
# MUSLIM FAMILY LAWS ORDINANCE, 1961
# ═══════════════════════════════════════════════════════════
MFLO_NAME = "Muslim Family Laws Ordinance"
MFLO_ALT = "Muslim Family Laws Ordinance, 1961"

mflo_sections = [
    ("4", "Succession", "In the event of death of any son or daughter before the opening of succession, the children of such son or daughter shall per stirpes receive the share of such deceased.", "وراثت کھلنے سے پہلے بیٹے یا بیٹی کی وفات کی صورت میں ان کے بچوں کو حصہ ملے گا۔"),
    ("5", "Registration of Marriages", "Every marriage solemnized under Muslim law shall be registered in accordance with the provisions of this Ordinance.", "اسلامی قانون کے تحت ہر نکاح اس آرڈیننس کے مطابق رجسٹرڈ ہوگا۔"),
    ("6", "Polygamy", "No man, during the subsistence of an existing marriage, shall contract another marriage without the previous permission in writing of the Arbitration Council.", "کوئی مرد موجود شادی کے دوران ثالثی کونسل کی تحریری اجازت کے بغیر دوسری شادی نہیں کرے گا۔"),
    ("7", "Talaq (Divorce)", "Any man who wishes to divorce his wife shall pronounce talaq in any form and give the Chairman notice in writing. Talaq shall not be effective until ninety days have elapsed.", "طلاق دینے والا مرد چیئرمین کو تحریری نوٹس دے گا۔ طلاق نوے دن گزرنے تک مؤثر نہیں ہوگی۔"),
    ("8", "Dissolution of Marriage Otherwise Than by Talaq", "Where the right to divorce has been duly delegated to the wife (talaq-e-tafweez), she may exercise it in the manner prescribed.", "جہاں طلاق کا حق بیوی کو تفویض کیا گیا ہو وہ مقررہ طریقے سے استعمال کر سکتی ہے۔"),
    ("9", "Maintenance", "If any husband fails to maintain his wife adequately, the wife may apply to the Chairman who shall constitute an Arbitration Council to determine the matter.", "شوہر نان و نفقہ نہ دے تو بیوی چیئرمین سے رجوع کر سکتی ہے۔"),
    ("10", "Dower (Mahr)", "Where no details about the mode of payment of dower are specified in the nikahnama, the entire amount of the dower shall be presumed to be payable on demand.", "نکاح نامے میں مہر کی ادائیگی کی تفصیلات نہ ہوں تو پوری رقم فوری طلب پر قابل ادائیگی ہوگی۔"),
]

# ═══════════════════════════════════════════════════════════
# PECA (Prevention of Electronic Crimes Act, 2016)
# ═══════════════════════════════════════════════════════════
PECA_NAME = "Prevention of Electronic Crimes Act"
PECA_ALT = "Prevention of Electronic Crimes Act, 2016"

peca_sections = [
    ("3", "Unauthorized Access to Information System", "Whoever intentionally gains unauthorized access to any information system or data shall be punished with imprisonment up to three months or fine up to fifty thousand rupees or both.", "غیر مجاز رسائی کی سزا تین ماہ قید یا پچاس ہزار جرمانہ یا دونوں ہے۔"),
    ("4", "Unauthorized Copying of Data", "Whoever intentionally and without authorization copies or transmits data shall be punished with imprisonment up to six months or fine up to one hundred thousand rupees or both.", "غیر مجاز ڈیٹا نقل کی سزا چھ ماہ قید یا ایک لاکھ جرمانہ ہے۔"),
    ("5", "Interference with Information System", "Whoever intentionally interferes with or damages any information system, causing it to malfunction, shall be punished.", "انفارمیشن سسٹم میں مداخلت یا نقصان سزا کا مستحق ہے۔"),
    ("6", "Unauthorized Access to Critical Infrastructure", "Whoever gains unauthorized access to any critical infrastructure information system shall be punished with imprisonment up to three years or fine up to one million rupees or both.", "اہم انفراسٹرکچر میں غیر مجاز رسائی کی سزا تین سال قید یا دس لاکھ جرمانہ ہے۔"),
    ("10", "Cyber Terrorism", "Whoever commits or threatens to commit any offence under this Act with intent to coerce, intimidate, or overawe the Government or the public or create a sense of fear or insecurity shall be punished with imprisonment up to fourteen years.", "سائبر دہشت گردی کی سزا چودہ سال تک قید ہے۔"),
    ("11", "Electronic Forgery", "Whoever intentionally creates, alters, or generates any electronic document with intent to commit fraud shall be punished with imprisonment up to three years or fine or both.", "الیکٹرانک جعل سازی کی سزا تین سال قید یا جرمانہ ہے۔"),
    ("12", "Electronic Fraud", "Whoever, with intent to defraud, interferes with or uses any information system, device or data, shall be punished with imprisonment up to two years or fine up to ten million rupees or both.", "الیکٹرانک فراڈ کی سزا دو سال قید یا ایک کروڑ جرمانہ ہے۔"),
    ("14", "Unauthorized Interception", "Whoever intentionally intercepts any communication through electromagnetic, acoustic, or other surveillance device shall be punished.", "غیر مجاز مواصلات کی نگرانی سزا کا مستحق ہے۔"),
    ("16", "Offences Against Dignity of a Natural Person", "Whoever intentionally and publicly exhibits or displays or transmits any information through any information system, which he knows to be false, and intimidates or harms the reputation of a natural person, shall be punished with imprisonment up to three years or fine up to one million rupees or both.", "کسی شخص کی عزت کو آن لائن نقصان پہنچانے کی سزا تین سال قید یا دس لاکھ جرمانہ ہے۔"),
    ("20", "Offences Against Modesty of Natural Person and Minor", "Whoever intentionally exhibits, transmits any sexually explicit image of a person without consent shall be punished with imprisonment up to five years or fine up to five million rupees or both.", "بغیر رضامندی فحش تصاویر شیئر کرنے کی سزا پانچ سال قید یا پچاس لاکھ جرمانہ ہے۔"),
    ("21", "Child Pornography", "Whoever intentionally produces, offers, distributes, or possesses child pornography through any information system shall be punished with imprisonment up to seven years or fine up to five million rupees or both.", "بچوں کی فحاشی سے متعلق مواد کی سزا سات سال قید یا پچاس لاکھ جرمانہ ہے۔"),
    ("22", "Malicious Code", "Whoever willfully writes, distributes or transmits a malicious code (virus, worm, trojan) that results in damage to any information system shall be punished.", "نقصاندہ کوڈ (وائرس) پھیلانے والا سزا کا مستحق ہے۔"),
    ("24", "Cyber Stalking", "Whoever with intent to coerce or intimidate or harass any person, uses information system, network or the internet, and follows the person, monitors, observes, threatens, shall be punished with imprisonment up to three years or fine up to one million rupees or both.", "سائبر اسٹاکنگ (آن لائن تعاقب) کی سزا تین سال قید یا دس لاکھ جرمانہ ہے۔"),
    ("25", "Spamming", "Whoever transmits harmful, fraudulent, misleading, illegal or unsolicited information to any person without permission shall be punished.", "بغیر اجازت فضول پیغامات بھیجنا سزا کا مستحق ہے۔"),
    ("26", "Spoofing", "Whoever establishes a website or sends information with a counterfeit source address with intent to unlawfully obtain sensitive information shall be punished.", "جعلی ذریعے سے معلومات حاصل کرنا (سپوفنگ) سزا کا مستحق ہے۔"),
]

# ═══════════════════════════════════════════════════════════
# CONTRACT ACT, 1872
# ═══════════════════════════════════════════════════════════
CONTRACT_NAME = "Contract Act"
CONTRACT_ALT = "Contract Act, 1872"

contract_sections = [
    ("2", "Interpretation", "When one person signifies to another his willingness to do or to abstain from doing anything, with a view to obtaining the assent of that other to such act or abstinence, he is said to make a proposal.", "جب کوئی شخص کسی فعل کے لیے رضامندی حاصل کرنے کی خاطر اپنی رضامندی ظاہر کرے تو یہ تجویز ہے۔"),
    ("10", "What Agreements are Contracts", "All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object.", "تمام معاہدے جو آزاد رضامندی، جائز عوض اور جائز مقصد سے ہوں، معاہدے ہیں۔"),
    ("11", "Who Are Competent to Contract", "Every person is competent to contract who is of the age of majority according to the law, is of sound mind, and is not disqualified from contracting by any law.", "ہر وہ شخص معاہدے کا اہل ہے جو بالغ ہو، ذہنی طور پر صحت مند ہو، اور قانون نے نااہل قرار نہ دیا ہو۔"),
    ("14", "Free Consent", "Consent is said to be free when it is not caused by coercion, undue influence, fraud, misrepresentation, or mistake.", "رضامندی آزاد ہے جب جبر، ناجائز اثر، فراڈ، غلط بیانی یا غلطی نہ ہو۔"),
    ("15", "Coercion", "Coercion is the committing, or threatening to commit, any act forbidden by the Pakistan Penal Code, or the unlawful detaining of any property.", "جبر سے مراد تعزیرات پاکستان کے تحت ممنوع فعل کرنا یا دھمکی دینا ہے۔"),
    ("16", "Undue Influence", "A contract is said to be induced by undue influence where the relations between the parties are such that one is in a position to dominate the will of the other.", "ناجائز اثر وہاں ہے جہاں ایک فریق دوسرے کی مرضی پر غلبہ رکھتا ہو۔"),
    ("17", "Fraud", "Fraud means and includes any act committed by a party to a contract with intent to deceive another party or to induce him to enter into the contract.", "فراڈ سے مراد دھوکہ دینے کی نیت سے کوئی فعل ہے۔"),
    ("23", "What Considerations and Objects are Lawful", "The consideration or object of an agreement is lawful, unless it is forbidden by law, defeats any law, is fraudulent, involves injury, or is opposed to public policy.", "معاہدے کا عوض جائز ہے سوائے اس کے کہ قانون نے منع کیا ہو، فراڈ ہو، یا عوامی پالیسی کے خلاف ہو۔"),
    ("25", "Agreement Without Consideration Void", "An agreement made without consideration is void, unless it is in writing and registered, or is a promise to compensate for something done, or is a promise made on account of natural love and affection.", "بغیر عوض کا معاہدہ کالعدم ہے، سوائے تحریری و رجسٹرڈ ہو یا قدرتی محبت پر ہو۔"),
    ("27", "Agreement in Restraint of Trade Void", "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void.", "جائز پیشے سے روکنے والا ہر معاہدہ کالعدم ہے۔"),
    ("56", "Agreement to Do Impossible Act", "An agreement to do an act impossible in itself is void. A contract to do an act which, after the contract is made, becomes impossible or unlawful, becomes void when the act becomes impossible or unlawful.", "ناممکن فعل کا معاہدہ کالعدم ہے۔"),
    ("73", "Compensation for Loss or Damage", "When a contract has been broken, the party who suffers by such breach is entitled to receive compensation for any loss or damage caused to him thereby.", "معاہدے کی خلاف ورزی سے متاثرہ فریق نقصان کا معاوضہ وصول کرنے کا حقدار ہے۔"),
    ("74", "Compensation for Breach Where Penalty Stipulated", "When a contract has been broken, and the contract contains a stipulation by way of penalty, the party complaining of the breach is entitled to receive reasonable compensation.", "جرمانے والے معاہدے کی خلاف ورزی پر متاثرہ فریق معقول معاوضے کا حقدار ہے۔"),
    ("124", "Contract of Indemnity", "A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor himself, or by the conduct of any other person, is called a contract of indemnity.", "ضمانت نقصان کا معاہدہ جس میں ایک فریق دوسرے کو نقصان سے بچانے کا وعدہ کرے۔"),
    ("148", "Duties of Bailee", "The bailee is bound to take as much care of the goods bailed to him as a man of ordinary prudence would take of his own goods.", "امین کو بیلی کی چیزوں کی اتنی ہی دیکھ بھال کرنی ہوگی جتنی وہ اپنی چیزوں کی کرتا ہے۔"),
]

# ═══════════════════════════════════════════════════════════
# OTHER STATUTES
# ═══════════════════════════════════════════════════════════
ANTI_TERROR_NAME = "Anti-Terrorism Act"
NAB_NAME = "National Accountability Ordinance"
FAMILY_COURTS_NAME = "West Pakistan Family Courts Act"
FAMILY_COURTS_ALT = "West Pakistan Family Courts Act, 1964"
QSO_NAME = "Qanun-e-Shahadat Order"
LIMITATION_NAME = "Limitation Act"
LIMITATION_ALT = "Limitation Act, 1908"
TPA_NAME = "Transfer of Property Act"
TPA_ALT = "Transfer of Property Act, 1882"
RELIEF_NAME = "Specific Relief Act"
RELIEF_ALT = "Specific Relief Act, 1877"

other_sections = [
    # Anti-Terrorism Act
    ("6", "Terrorist Act", "Any person who commits a terrorist act shall be guilty of the offence of terrorism and is liable to imprisonment for life, or imprisonment up to fourteen years.", "دہشت گردی کا فعل کرنے والا عمر قید یا چودہ سال تک قید کا مستحق ہے۔", ANTI_TERROR_NAME, "CRIMINAL"),
    ("7", "Punishment for Terrorism", "A person guilty of an offence of terrorism under section 6 shall be liable to death, life imprisonment, or imprisonment which may extend to fourteen years and fine.", "دہشت گردی کی سزا موت، عمر قید، یا چودہ سال قید اور جرمانہ ہے۔", ANTI_TERROR_NAME, "CRIMINAL"),
    ("11", "Action in Aid of Civil Power", "When the Armed Forces are called in aid of civil power, certain provisions of this Act shall apply.", "مسلح افواج شہری حکومت کی مدد میں بلائی جائیں تو اس ایکٹ کی شقیں لاگو ہوں گی۔", ANTI_TERROR_NAME, "CRIMINAL"),
    # NAB Ordinance
    ("9", "Offences Triable by Accountability Court", "An offence of corruption and corrupt practices shall be triable only by the Accountability Court.", "بدعنوانی کے مقدمات صرف احتساب عدالت میں سنے جائیں گے۔", NAB_NAME, "CRIMINAL"),
    ("10", "Cognizance of Offences by Court", "The Accountability Court shall not take cognizance of any offence except on a reference made by the National Accountability Bureau.", "احتساب عدالت نیب کے ریفرنس کے بغیر نوٹس نہیں لے گی۔", NAB_NAME, "CRIMINAL"),
    ("14", "Plea Bargain", "At any stage of investigation or proceedings, the Chairman NAB may accept from the accused person, a plea bargain whereby the accused person agrees to return the assets or gains of corruption.", "تحقیقات کے کسی مرحلے پر ملزم پلی بارگین کر سکتا ہے۔", NAB_NAME, "CRIMINAL"),
    # Family Courts Act
    ("5", "Jurisdiction of Family Court", "Subject to the provisions of the Ordinance, the Family Court shall have exclusive jurisdiction to entertain and adjudicate matters involving dissolution of marriage, dower, maintenance, restitution of conjugal rights, custody of children.", "فیملی کورٹ کو فسخ نکاح، مہر، نفقہ، بحالی ازدواجی حقوق، حضانت کے معاملات میں خصوصی دائرہ اختیار ہے۔", FAMILY_COURTS_NAME, "FAMILY"),
    ("7", "Pre-Trial Proceedings", "When the written statement has been filed, the Family Court shall fix a date for pre-trial hearing and attempt reconciliation.", "تحریری جواب داخل ہونے پر فیملی کورٹ قبل از سماعت صلح کی کوشش کرے گی۔", FAMILY_COURTS_NAME, "FAMILY"),
    ("10", "Procedure of Family Court", "The Family Court may follow such procedure as it may deem fit and shall not be bound by the Code of Civil Procedure.", "فیملی کورٹ ضابطہ دیوانی سے پابند نہیں ہے اور مناسب طریقہ اختیار کر سکتی ہے۔", FAMILY_COURTS_NAME, "FAMILY"),
    ("12", "Appeal", "An appeal shall lie from the decree of the Family Court to the High Court within thirty days.", "فیملی کورٹ کے فیصلے کے خلاف تیس دن میں ہائی کورٹ میں اپیل ہو سکتی ہے۔", FAMILY_COURTS_NAME, "FAMILY"),
    # Qanun-e-Shahadat
    ("2", "Relevancy of Facts", "Evidence may be given in any suit or proceeding of the existence or non-existence of every fact in issue and of such other facts as are relevant.", "مقدمے میں ہر متعلقہ حقیقت کا ثبوت دیا جا سکتا ہے۔", QSO_NAME, "CIVIL"),
    ("3", "Qanun-e-Shahadat to Apply to All Proceedings", "This Order shall apply to all judicial and legal proceedings.", "قانون شہادت تمام عدالتی اور قانونی کارروائیوں پر لاگو ہوگا۔", QSO_NAME, "CIVIL"),
    ("17", "Competence and Number of Witnesses", "The competence of a person to testify shall be determined by the Court. In matters of financial obligation, two men or one man and two women are required.", "گواہ کی اہلیت عدالت طے کرے گی۔ مالی معاملات میں دو مرد یا ایک مرد اور دو خواتین ضروری ہیں۔", QSO_NAME, "CIVIL"),
    ("46", "Facts Judicially Noticeable Need Not be Proved", "No fact of which the Court will take judicial notice need be proved.", "عدالتی طور پر معلوم حقائق کو ثابت کرنے کی ضرورت نہیں۔", QSO_NAME, "CIVIL"),
    ("59", "Proof of Facts by Oral Evidence", "All facts, except the contents of documents, may be proved by oral evidence.", "دستاویزات کے مندرجات کے علاوہ تمام حقائق زبانی ثبوت سے ثابت ہو سکتے ہیں۔", QSO_NAME, "CIVIL"),
    ("79", "Presumption as to Genuineness of Certified Copies", "The Court shall presume every document purporting to be a certificate, certified copy or other document, to be genuine.", "تصدیق شدہ نقل کو اصلی مانا جائے گا۔", QSO_NAME, "CIVIL"),
    ("114", "Presumption - Court May Presume Existence of Certain Facts", "The Court may presume the existence of any fact which it thinks likely to have happened, regard being had to the common course of natural events.", "عدالت قدرتی واقعات کے مطابق کچھ حقائق کا اندازہ لگا سکتی ہے۔", QSO_NAME, "CIVIL"),
    ("129", "Privilege - Confidential Communication During Marriage", "No person who is or has been married shall be compelled to disclose any communication made to him during marriage by any person to whom he is or has been married.", "شادی کے دوران ذاتی بات چیت ظاہر کرنے پر مجبور نہیں کیا جا سکتا۔", QSO_NAME, "CIVIL"),
    # Limitation Act
    ("3", "Bar of Limitation", "Every suit instituted, appeal or application made after the prescribed period of limitation shall be dismissed.", "مقررہ مدت کے بعد دائر کیا گیا ہر مقدمہ خارج ہوگا۔", LIMITATION_NAME, "CIVIL"),
    ("5", "Extension of Prescribed Period", "Any appeal or application may be admitted after the prescribed period if the appellant or applicant satisfies the court that he had sufficient cause for not making it within such period.", "اگر معقول وجہ ہو تو عدالت تاخیر معاف کر سکتی ہے۔", LIMITATION_NAME, "CIVIL"),
    ("12", "Exclusion of Time in Computing Period of Limitation", "In computing the period of limitation, the day from which such period is to be reckoned shall be excluded.", "مدت شمار کرنے میں ابتدائی دن شامل نہیں ہوگا۔", LIMITATION_NAME, "CIVIL"),
    ("14", "Exclusion of Time for Proceeding in Wrong Court", "In computing the period of limitation, the time during which the applicant was prosecuting with due diligence another proceeding in a court which lacked jurisdiction shall be excluded.", "غلط عدالت میں کارروائی کا وقت مدت سے خارج ہوگا۔", LIMITATION_NAME, "CIVIL"),
    # Transfer of Property Act
    ("5", "Transfer of Property Defined", "Transfer of property means an act by which a living person conveys property to one or more living persons.", "منتقلی ملکیت سے مراد وہ فعل ہے جس سے زندہ شخص دوسرے زندہ شخص کو جائیداد دے۔"),
    ("54", "Sale Defined", "Sale is a transfer of ownership in exchange for a price paid or promised.", "فروخت سے مراد قیمت کے عوض ملکیت کی منتقلی ہے۔"),
    ("58", "Mortgage Defined", "A mortgage is the transfer of an interest in specific immovable property for the purpose of securing the payment of money.", "رہن سے مراد قرض کی واپسی کی ضمانت کے لیے غیر منقولہ جائیداد میں حق کی منتقلی ہے۔"),
    ("105", "Lease Defined", "A lease of immoveable property is a transfer of a right to enjoy such property, made for a certain time, in consideration of a price paid or promised.", "پٹہ غیر منقولہ جائیداد سے فائدہ اٹھانے کے حق کی مقررہ مدت کے لیے منتقلی ہے۔"),
    ("106", "Duration of Certain Leases", "In the absence of a contract or local usage, a lease of immoveable property for agricultural or manufacturing purposes shall be deemed to be a lease from year to year.", "معاہدے کے بغیر زرعی پٹہ سالانہ تصور ہوگا۔"),
    # Specific Relief Act
    ("9", "Suit for Recovery of Specific Immoveable Property", "If any person is dispossessed without his consent of immoveable property, he may sue for recovery of possession.", "ناجائز قبضے سے بے دخل شخص قبضے کی واپسی کا دعویٰ کر سکتا ہے۔"),
    ("12", "Specific Performance of Contract", "Specific performance of a contract shall be enforced when the act agreed to be done is such that compensation in money for its non-performance would not afford adequate relief.", "جب رقم سے مناسب معاوضہ ممکن نہ ہو تو عدالت معاہدے کے عین مطابق عمل کا حکم دے سکتی ہے۔"),
    ("42", "Declaratory Decree", "Any person entitled to any legal character, or to any right as to any property, may institute a suit against any person denying, or interested to deny, his title to such character or right.", "قانونی حیثیت یا حق کے بارے میں اعلانیہ حکم نامے کا دعویٰ کیا جا سکتا ہے۔"),
    ("54", "Preventive Relief - Temporary Injunction", "Temporary injunctions are such as are to continue until a specified time, or until the further order of the Court.", "عارضی حکم امتناعی مخصوص مدت یا عدالت کے مزید حکم تک جاری رہتا ہے۔"),
    ("56", "Perpetual Injunction", "A perpetual injunction can only be granted by the decree made at the hearing and upon the merits of the suit.", "مستقل حکم امتناعی صرف مقدمے کی سماعت کے بعد جاری ہوتا ہے۔"),
]


async def insert_sections():
    async with async_session() as db:
        # Get statute name -> id map
        result = await db.execute(text("SELECT id, title FROM statutes"))
        statute_map = {}
        for row in result.fetchall():
            statute_map[row[1]] = row[0]
            # Also map without year suffix
            clean = row[1].split(',')[0].strip()
            if clean not in statute_map:
                statute_map[clean] = row[0]

        # Get existing section count
        existing = (await db.execute(text("SELECT COUNT(*) FROM sections"))).scalar()
        print(f"Existing sections: {existing}")

        # Build all sections
        all_sections = []

        # PPC
        for s in ppc_sections:
            sid = statute_map.get(PPC_NAME) or statute_map.get(PPC_ALT)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "CRIMINAL"))

        # CrPC
        for s in crpc_sections:
            sid = statute_map.get(CRPC_NAME) or statute_map.get(CRPC_ALT)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "CRIMINAL"))

        # Constitution
        for s in const_sections:
            sid = statute_map.get(CONST_NAME)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "CONSTITUTIONAL"))

        # MFLO
        for s in mflo_sections:
            sid = statute_map.get(MFLO_NAME) or statute_map.get(MFLO_ALT)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "FAMILY"))

        # PECA
        for s in peca_sections:
            sid = statute_map.get(PECA_NAME) or statute_map.get(PECA_ALT)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "CYBER"))

        # Contract Act
        for s in contract_sections:
            sid = statute_map.get(CONTRACT_NAME) or statute_map.get(CONTRACT_ALT)
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], "CIVIL"))

        # Other statutes (have statute_name in tuple)
        for s in other_sections:
            if len(s) == 6:
                statute_name, category = s[4], s[5]
            else:
                # TPA / Specific Relief (no explicit statute_name)
                if "transfer" in s[1].lower() or "sale" in s[1].lower() or "mortgage" in s[1].lower() or "lease" in s[1].lower():
                    statute_name = TPA_NAME
                    category = "PROPERTY"
                else:
                    statute_name = RELIEF_NAME
                    category = "CIVIL"

            sid = statute_map.get(statute_name)
            if not sid:
                # Try alt names
                for alt in [statute_name + ", 1877", statute_name + ", 1882", statute_name + ", 1908", statute_name + ", 1964", statute_name + ", 1999"]:
                    sid = statute_map.get(alt)
                    if sid:
                        break
            if sid:
                all_sections.append((sid, s[0], s[1], s[2], s[3], category))

        print(f"Total sections to insert: {len(all_sections)}")

        # Delete existing and re-insert
        await db.execute(text("DELETE FROM sections"))
        print("Cleared existing sections")

        inserted = 0
        for sec in all_sections:
            try:
                await db.execute(
                    text("""INSERT INTO sections (statute_id, section_number, title, content, content_ur, created_at)
                            VALUES (:sid, :num, :title, :content, :ur, NOW())"""),
                    {"sid": sec[0], "num": sec[1], "title": sec[2], "content": sec[3], "ur": sec[4]}
                )
                inserted += 1
            except Exception as e:
                print(f"Error inserting section {sec[1]}: {e}")

        await db.commit()
        print(f"Successfully inserted {inserted} sections")


if __name__ == "__main__":
    asyncio.run(insert_sections())
