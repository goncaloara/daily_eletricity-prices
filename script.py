import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime as dt
from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter
import numpy as np
from pathlib import Path

# Constants
DATA_FILE = Path("precos_eletricidade_omie.csv")
DAYS_TO_CHECK = 7  # Check last 7 days to catch any missing data


def load_existing_data():
    """Carrega dados existentes do arquivo CSV se existir."""
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE, parse_dates=['DATETIME'])
        print(
            f"\nDados existentes carregados: {len(df)} registos (de {df['DATETIME'].min().date()} a {df['DATETIME'].max().date()})")
        return df
    return None


def get_new_dates_needed(existing_data):
    """Determina quais datas precisam ser baixadas."""
    end_date = dt.date.today()

    if existing_data is None:
        start_date = dt.date(2023, 1, 1)
        print("\nNenhum dado existente encontrado. Baixando todos os dados desde 2023...")
    else:
        last_date = existing_data['DATETIME'].max().date()
        start_date = max(last_date - dt.timedelta(days=DAYS_TO_CHECK), dt.date(2023, 1, 1))
        print(f"\nVerificando dados desde {start_date} para atualizações...")

    return start_date, end_date


def fetch_new_data(start_date, end_date):
    """Baixa novos dados OMIE para o intervalo especificado."""
    try:
        print(f"\nBaixando dados de {start_date} a {end_date}...")
        importer = OMIEMarginalPriceFileImporter(date_ini=start_date, date_end=end_date)
        raw_data = importer.read_to_dataframe(verbose=False)

        if raw_data.empty:
            print("Nenhum dado novo encontrado.")
            return None

        def process_omie_data(df):
            df = df[df['CONCEPT'].isin(['PRICE_PT', 'PRICE_SP'])]
            hourly_cols = [f'H{i}' for i in range(1, 25)]
            melted = df.melt(
                id_vars=['DATE', 'CONCEPT'],
                value_vars=hourly_cols,
                var_name='HOUR',
                value_name='PRICE'
            )
            melted['PRICE'] = pd.to_numeric(melted['PRICE'], errors='coerce')
            melted['DATE'] = pd.to_datetime(melted['DATE'])
            melted['HOUR'] = melted['HOUR'].str.extract('(\d+)').astype(int)
            melted['DATETIME'] = melted['DATE'] + pd.to_timedelta(melted['HOUR'], unit='h')
            melted['COUNTRY'] = np.where(melted['CONCEPT'] == 'PRICE_PT', 'portugal', 'espanha')
            return melted[['DATETIME', 'COUNTRY', 'PRICE']].dropna()

        processed_data = process_omie_data(raw_data)
        print(f"Dados novos processados: {len(processed_data)} registos")
        return processed_data

    except Exception as e:
        print(f"\nErro ao baixar dados: {str(e)}")
        return None


def update_data():
    """Atualiza os dados existentes com novas informações."""
    existing_data = load_existing_data()
    start_date, end_date = get_new_dates_needed(existing_data)
    new_data = fetch_new_data(start_date, end_date)

    if new_data is None:
        return existing_data

    if existing_data is not None:
        combined = pd.concat([existing_data, new_data])
        combined = combined.drop_duplicates(subset=['DATETIME', 'COUNTRY'], keep='last')
        combined = combined.sort_values('DATETIME')
        print(
            f"\nDados combinados: {len(combined)} registos (de {combined['DATETIME'].min().date()} a {combined['DATETIME'].max().date()})")
        return combined

    return new_data


def create_visualization(data_source):
    """Cria visualização dos dados com tratamento adequado de datas."""
    data_source['DATE'] = data_source['DATETIME'].dt.date
    daily = data_source.groupby(['DATE', 'COUNTRY'])['PRICE'].mean().reset_index()

    min_date = daily['DATE'].min()
    max_date = daily['DATE'].max()
    all_dates = pd.date_range(start=min_date, end=max_date, freq='D').date

    pivot_df = daily.pivot(index='DATE', columns='COUNTRY', values='PRICE')
    pivot_df = pivot_df.reindex(all_dates)
    pivot_df = pivot_df.reset_index().rename(columns={'index': 'DATE'})
    pivot_df['DIFF'] = pivot_df['portugal'] - pivot_df['espanha']

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Preço Diário ({min_date.year}-{max_date.year})",
            f"Diferença PT-ES ({min_date.year}-{max_date.year})"
        ),
        horizontal_spacing=0.15
    )

    for country, color, name in [('portugal', '#FF7F0E', 'Portugal'), ('espanha', '#1F77B4', 'Espanha')]:
        fig.add_trace(go.Bar(
            x=pivot_df['DATE'],
            y=pivot_df[country],
            name=name,
            marker_color=color,
            opacity=0.7,
            hovertemplate=(
                f"<b>{name}</b><br>"
                "%{x|%d-%m-%Y}<br>"
                "€%{y:.2f}/MWh<extra></extra>"
            )
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=pivot_df['DATE'],
        y=pivot_df['DIFF'],
        name='Diferença PT-ES',
        line=dict(color='#2CA02C', width=1.5),
        mode='lines',
        hovertemplate=(
            "<b>Diferença</b><br>"
            "%{x|%d-%m-%Y}<br>"
            "€%{y:.2f}/MWh<extra></extra>"
        )
    ), row=1, col=2)

    fig.update_layout(
        title_text=f"Evolução dos Preços de Eletricidade (Atualizado: {dt.date.today().strftime('%d/%m/%Y')})",
        title_x=0.5,
        plot_bgcolor='white',
        hovermode='x unified',
        barmode='group',
        height=600,
        margin=dict(l=50, r=50, b=100, t=100, pad=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    fig.update_xaxes(
        title_text="Data",
        tickformat='%Y-%m',
        rangeslider=dict(visible=True, thickness=0.05),
        row=1, col=1
    )
    fig.update_xaxes(
        title_text="Data",
        tickformat='%Y-%m',
        rangeslider=dict(visible=True, thickness=0.05),
        row=1, col=2
    )

    fig.update_yaxes(title_text="Preço (€/MWh)", row=1, col=1)
    fig.update_yaxes(title_text="Diferença (€/MWh)", row=1, col=2)

    return fig


def main():
    try:
        data = update_data()

        if data is None or data.empty:
            raise ValueError("Nenhum dado disponível para visualização")

        data.to_csv(DATA_FILE, index=False)
        print(f"\nDados guardados em '{DATA_FILE}'")

        print("\nA criar visualização...")
        fig = create_visualization(data)

        # Save HTML in the same folder as the script
        script_dir = Path(__file__).parent
        output_file = script_dir / 'visualizacao_precos_eletricidade.html'
        fig.write_html(
            output_file,
            config={'scrollZoom': True},
            include_plotlyjs='cdn',
            full_html=False
        )
        print(f"\nVisualização guardada em '{output_file}'")

        try:
            import webbrowser
            webbrowser.open(str(output_file))
        except:
            pass

        fig.show()

    except Exception as e:
        print(f"\nErro: {str(e)}")


if __name__ == "__main__":
    main()