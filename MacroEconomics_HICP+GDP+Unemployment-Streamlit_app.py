import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- Detectar país desde dirección ---
def obtener_codigo_pais(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "macro-app/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers)
        data = r.json()
        if data:
            return data[0]["address"].get("country_code", "").upper()
    except Exception as e:
        st.error(f"Error detectando país: {e}")
    return None

# --- Interfaz ---
st.title("📊 Macroeconomic Summary Generator (HICP + GDP + Unemployment)")
direccion = st.text_input("Enter a European address:")
longitud = st.slider("Number of words in the summary:", 100, 300, 150, step=25)
kpis_seleccionados = st.multiselect(
    "Select the indicators to include in the summary:",
    ["HICP – Harmonized Inflation", "GDP – Gross Domestic Product", "Unemployment Rate"]
)

# --- Procesamiento ---
if st.button("Generate Summary") and direccion and kpis_seleccionados:
    codigo_pais = obtener_codigo_pais(direccion)
    if not codigo_pais:
        st.error("❌ Could not detect the country.")
    else:
        nombre_pais = {
            "NL": "Países Bajos", "ES": "España", "FR": "Francia",
            "IT": "Italia", "DE": "Alemania", "BE": "Bélgica"
        }.get(codigo_pais, f"País ({codigo_pais})")

        anio_corte = datetime.today().year - 5

        def obtener_df(dataset, extra_params, periodo="Q"):
            url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
            params = {"format": "JSON", "lang": "EN", "geo": codigo_pais}
            params.update(extra_params)
            r = requests.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            idx = data["dimension"]["time"]["category"]["index"]
            lbl = data["dimension"]["time"]["category"]["label"]
            ix_map = {str(v): lbl[k] for k, v in idx.items()}
            valores = [{"Periodo": ix_map[k], "Valor": v} for k, v in data["value"].items()]
            df = pd.DataFrame(valores)
            df = df[df["Periodo"].str[:4].astype(int) >= anio_corte]
            df["Periodo"] = pd.PeriodIndex(df["Periodo"], freq=periodo).astype(str)
            return df

        texto_kpis = ""
        parrafos_es = []
        parrafos_en = []
        resumen_idx = 0

        try:
            if "HICP – Harmonized Inflation" in kpis_seleccionados:
                df_hicp = obtener_df("prc_hicp_midx", {"coicop": "CP00", "unit": "I15"})
                texto_kpis += f"\n\n📌 HICP – Harmonized Inflation Index:\n{df_hicp.to_string(index=False)}"

            if "GDP – Gross Domestic Product" in kpis_seleccionados:
                df_pib = obtener_df("namq_10_gdp", {"na_item": "B1GQ", "unit": "CLV10_MNAC", "s_adj": "NSA"})
                texto_kpis += f"\n\n📌 GDP – Quarterly Volume:\n{df_pib.to_string(index=False)}"

            if "Unemployment Rate" in kpis_seleccionados:
                df_unemp = obtener_df("une_rt_m", {
                    "unit": "PC_ACT", "sex": "T", "age": "TOTAL", "s_adj": "SA"
                }, periodo="M")
                texto_kpis += f"\n\n📌 Unemployment Rate:\n{df_unemp.to_string(index=False)}"

            # --- Prompts ---
            prompt_es = f"""
Eres un economista. Redacta un resumen técnico de aproximadamente {longitud} palabras sobre los siguientes indicadores reales de {nombre_pais} obtenidos de Eurostat:

{texto_kpis}

Escribe un párrafo separado por cada KPI, y concluye con un párrafo final que los relacione. El texto debe estar en español.
"""

            prompt_en = f"""
You are an economist. Write a technical summary of approximately {longitud} words about the following real indicators for {nombre_pais}, sourced from Eurostat:

{texto_kpis}

Write a separate paragraph for each KPI, and finish with a final paragraph that connects them. The text must be in English.
"""

            resp_es = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_es}],
                temperature=0.6
            )
            resp_en = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_en}],
                temperature=0.6
            )

            parrafos_es = resp_es.choices[0].message.content.strip().split("\n\n")
            parrafos_en = resp_en.choices[0].message.content.strip().split("\n\n")

            st.markdown("## 📊 Results by Indicator")
            idx = 0
            if "HICP – Harmonized Inflation" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    st.markdown("#### HICP – Harmonized Inflation")
                    fig, ax = plt.subplots(figsize=(6, 3))
                    ax.plot(df_hicp["Periodo"], df_hicp["Valor"], color="#DAA520")
                    ax.set_facecolor("#F5F5F5")
                    ax.grid(True, linestyle="--", alpha=0.3)
                    ax.tick_params(axis="x", rotation=45)
                    st.pyplot(fig)
                with col2:
                    st.markdown("#### 🧠 Summary – ES")
                    st.write(parrafos_es[idx])
                    st.markdown("#### 🧠 Summary – EN")
                    st.write(parrafos_en[idx])
                    idx += 1

            if "GDP – Gross Domestic Product" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    st.markdown("#### GDP – Gross Domestic Product")
                    fig, ax = plt.subplots(figsize=(6, 3))
                    ax.plot(df_pib["Periodo"], df_pib["Valor"], color="#4682B4")
                    ax.set_facecolor("#F5F5F5")
                    ax.grid(True, linestyle="--", alpha=0.3)
                    ax.tick_params(axis="x", rotation=45)
                    st.pyplot(fig)
                with col2:
                    st.markdown("#### 🧠 Summary – ES")
                    st.write(parrafos_es[idx])
                    st.markdown("#### 🧠 Summary – EN")
                    st.write(parrafos_en[idx])
                    idx += 1

            if "Unemployment Rate" in kpis_seleccionados:
                col1, col2 = st.columns([1.2, 2])
                with col1:
                    st.markdown("#### Unemployment Rate")
                    fig, ax = plt.subplots(figsize=(6, 3))
                    ax.plot(df_unemp["Periodo"], df_unemp["Valor"], color="#2F4F4F")
                    ax.set_facecolor("#F5F5F5")
                    ax.grid(True, linestyle="--", alpha=0.3)
                    ax.tick_params(axis="x", rotation=45)
                    st.pyplot(fig)
                with col2:
                    st.markdown("#### 🧠 Summary – ES")
                    st.write(parrafos_es[idx])
                    st.markdown("#### 🧠 Summary – EN")
                    st.write(parrafos_en[idx])
                    idx += 1

            # --- Conclusión final
            st.markdown("## 🧩 Final Conclusion")
            st.markdown("#### 🧠 Conclusión – ES")
            st.write(parrafos_es[-1])
            st.markdown("#### 🧠 Conclusion – EN")
            st.write(parrafos_en[-1])

        except Exception as e:
            st.error(f"❌ Error al procesar: {e}")



