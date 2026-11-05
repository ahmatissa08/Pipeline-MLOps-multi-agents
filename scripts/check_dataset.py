from core.storage import read_csv

df = read_csv("raw-data", "adult/adult_v1.csv")
print("Dimensions :", df.shape)
print("\nValeurs manquantes par colonne :")
print(df.isna().sum()[lambda s: s > 0])
print("\nDoublons :", df.duplicated().sum())
print("\nRépartition de la cible :")
print(df["class"].value_counts(normalize=True).round(3))
print("\nPart de >50K selon le sexe :")
print(df.groupby("sex")["class"].apply(lambda s: (s == ">50K").mean()).round(3))