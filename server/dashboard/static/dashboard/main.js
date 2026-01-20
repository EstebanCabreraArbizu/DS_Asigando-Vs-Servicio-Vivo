/**
 * Dashboard PA vs SV - Main JavaScript
 * Separado de main.html para mejor mantenibilidad
 */

// ===== ESTADO GLOBAL =====
        let currentPeriod = null;
        let currentPage = 1;
        let sortBy = 'Personal_Real';
        let sortOrder = 'desc';
        let metricsData = null;
        let chartsInstances = {};

        // Estado de paginación para tablas
        let clientPage = 1;
        let unitPage = 1;
        let servicePage = 1;
        const perPage = 25;

        // ===== TABLE HEADER STYLE ENFORCER =====
        function enforceTableHeaderStyles() {
            // Force apply dark theme to all table headers
            const style = document.createElement('style');
            style.id = 'table-header-overrides';
            style.textContent = `
                html body table thead th,
                html body table thead tr th,
                html body .table-fixed-header thead th,
                html body .table-fixed-header thead tr th,
                html body .min-w-full thead th,
                html body .min-w-full thead tr th {
                    color: #f3f7ff !important;
                    background-color: #0a0f1f !important;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.16) !important;
                    letter-spacing: 0.08em !important;
                    padding: 1rem 0.75rem !important;
                    font-weight: 600 !important;
                    text-transform: uppercase !important;
                    font-size: 0.85rem !important;
                }
                html body table thead th.text-right,
                html body table thead th.text-center {
                    text-align: right !important;
                    color: #f3f7ff !important;
                    background-color: #0a0f1f !important;
                }
                html body table thead th.text-center {
                    text-align: center !important;
                }
                html body th[class*="text-gray"],
                html body th[class*="bg-"],
                html body thead[class*="bg-"],
                html body .bg-gray-50 {
                    color: #f3f7ff !important;
                    background-color: #0a0f1f !important;
                }
                html body .table-fixed-header thead {
                    backdrop-filter: blur(10px) !important;
                    -webkit-backdrop-filter: blur(10px) !important;
                    background: linear-gradient(120deg, rgba(255, 44, 85, 0.25), rgba(0, 247, 255, 0.12)) !important;
                }
                html body table thead th:hover {
                    background-color: rgba(255, 44, 85, 0.2) !important;
                    color: #f3f7ff !important;
                }
            `;

            // Remove existing style if present
            const existingStyle = document.getElementById('table-header-overrides');
            if (existingStyle) {
                existingStyle.remove();
            }

            // Add new style
            document.head.appendChild(style);

            // Also directly apply styles to existing table headers
            document.querySelectorAll('table thead th').forEach(th => {
                th.style.color = '#f3f7ff';
                th.style.backgroundColor = '#0a0f1f';
                th.style.borderBottom = '1px solid rgba(255, 255, 255, 0.16)';
                th.style.letterSpacing = '0.08em';
                th.style.padding = '1rem 0.75rem';
                th.style.fontWeight = '600';
                th.style.textTransform = 'uppercase';
                th.style.fontSize = '0.85rem';
            });

            // Apply to thead containers
            document.querySelectorAll('table thead').forEach(thead => {
                thead.style.backgroundColor = '#0a0f1f';
            });
        }

        // ===== INICIALIZACIÓN =====
        document.addEventListener('DOMContentLoaded', async () => {
            // Force reload CSS to ensure latest styles
            const links = document.querySelectorAll('link[href*="main.css"]');
            links.forEach(link => {
                const href = link.href;
                link.href = href + '&t=' + Date.now();
            });

            // Enforce table header styles immediately
            enforceTableHeaderStyles();

            setupTabs();
            setupEventListeners();
            await loadPeriods();

            // Re-enforce styles after initial load
            setTimeout(enforceTableHeaderStyles, 100);
        });

        // ===== TABS =====
        function setupTabs() {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('tab-active'));
                    btn.classList.add('tab-active');

                    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
                    document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');

                    // Resize charts cuando cambia de tab
                    setTimeout(() => {
                        Object.values(chartsInstances).forEach(chart => chart && chart.resize());
                    }, 100);

                    // Cargar datos específicos del tab si es necesario
                    if (btn.dataset.tab === 'detalle' && metricsData) {
                        loadTableData();
                    }
                    if (btn.dataset.tab === 'clientes' && metricsData) {
                        loadClientData();
                    }
                    if (btn.dataset.tab === 'unidades' && metricsData) {
                        loadUnitData();
                    }
                    if (btn.dataset.tab === 'servicios' && metricsData) {
                        loadServiceData();
                    }

                    // Re-enforce table header styles after tab switch
                    setTimeout(enforceTableHeaderStyles, 50);
                });
            });
        }

        // ===== CARGAR PERIODOS =====
        async function loadPeriods() {
            try {
                const response = await fetch('/dashboard/api/periods/?tenant=default');
                const data = await response.json();
                const select = document.getElementById('period-select');
                const select1 = document.getElementById('compare-period1');
                const select2 = document.getElementById('compare-period2');

                select.innerHTML = '';
                select1.innerHTML = '';
                select2.innerHTML = '';

                if (data.periods?.length > 0) {
                    data.periods.forEach((p, i) => {
                        const opt = `<option value="${p.value}">${p.label}</option>`;
                        select.innerHTML += opt;
                        select1.innerHTML += opt;
                        select2.innerHTML += opt;
                    });
                    if (data.periods.length > 1) select2.selectedIndex = 1;

                    currentPeriod = data.periods[0].value;
                    await loadMetrics(currentPeriod);
                } else {
                    select.innerHTML = '<option value="">Sin datos</option>';
                }
            } catch (err) {
                console.error('Error cargando periodos:', err);
            }
        }

        // ===== CARGAR MÉTRICAS =====
        async function loadMetrics(period) {
            showLoading(true);
            try {
                // Construir URL con filtros
                const params = new URLSearchParams({
                    tenant: 'default',
                    period: period
                });

                // Agregar filtros seleccionados
                const macrozona = document.getElementById('filter-macrozona').value;
                const zona = document.getElementById('filter-zona').value;
                const compania = document.getElementById('filter-compania').value;
                const grupo = document.getElementById('filter-grupo').value;
                const sector = document.getElementById('filter-sector').value;
                const gerente = document.getElementById('filter-gerente').value;

                if (macrozona) params.append('macrozona', macrozona);
                if (zona) params.append('zona', zona);
                if (compania) params.append('compania', compania);
                if (grupo) params.append('grupo', grupo);
                if (sector) params.append('sector', sector);
                if (gerente) params.append('gerente', gerente);

                const response = await fetch(`/dashboard/api/metrics/?${params.toString()}`);
                metricsData = await response.json();

                if (metricsData.error) {
                    showNoData();
                    return;
                }

                updateKPIs(metricsData.kpis);
                updateFilters(metricsData.filtros_disponibles);
                renderAllCharts(metricsData);
                updateTables(metricsData.charts);

                // Recargar datos paginados si estamos en esas pestañas
                const activeTab = document.querySelector('.tab-btn.tab-active');
                if (activeTab) {
                    const tabName = activeTab.dataset.tab;
                    if (tabName === 'clientes') loadClientData();
                    if (tabName === 'unidades') loadUnitData();
                    if (tabName === 'servicios') loadServiceData();
                }

            } catch (err) {
                console.error('Error cargando métricas:', err);
            } finally {
                showLoading(false);
            }
        }

        // ===== ACTUALIZAR KPIs =====
        function updateKPIs(kpis) {
            document.getElementById('kpi-pa').textContent = formatNumber(kpis.total_personal_asignado);
            document.getElementById('kpi-sv').textContent = formatNumber(kpis.total_servicio_vivo);
            document.getElementById('kpi-diff').textContent = formatNumber(kpis.diferencia_total);
            document.getElementById('kpi-coverage').textContent = `${kpis.cobertura_porcentaje}%`;
            document.getElementById('kpi-diff-pct').textContent = `${kpis.cobertura_diferencial || 0}%`;
            document.getElementById('kpi-servicios').textContent = formatNumber(kpis.total_servicios);
        }

        // ===== ACTUALIZAR FILTROS =====
        // Variable para controlar si es la primera carga
        let isFirstLoad = true;

        function updateFilters(filtros) {
            if (!filtros) return;

            const updateSelect = (id, values, label) => {
                const select = document.getElementById(id);
                const currentValue = select.value;  // Guardar valor actual

                select.innerHTML = `<option value="">${label} - Todas</option>`;
                (values || []).forEach(v => {
                    select.innerHTML += `<option value="${v}">${v}</option>`;
                });

                // Restaurar valor si existía y es la primera carga
                // En cargas subsiguientes (filtrado), mantener el valor seleccionado
                if (currentValue && !isFirstLoad) {
                    select.value = currentValue;
                }
            };

            updateSelect('filter-macrozona', filtros.macrozona, 'Macro Zona');
            updateSelect('filter-zona', filtros.zona, 'Zona');
            updateSelect('filter-compania', filtros.compania, 'Compañía');
            updateSelect('filter-grupo', filtros.grupo, 'Grupo');
            updateSelect('filter-sector', filtros.sector, 'Sector');
            updateSelect('filter-gerente', filtros.gerente, 'Gerente');

            isFirstLoad = false;
        }

        // ===== RENDERIZAR TODOS LOS GRÁFICOS =====
        function renderAllCharts(data) {
            const charts = data.charts;
            const kpis = data.kpis;

            // Gráfico Estado (Bar)
            chartsInstances.estado = echarts.init(document.getElementById('chart-estado'));
            if (charts.by_estado?.length > 0) {
                chartsInstances.estado.setOption({
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (params) {
                            let res = `<strong>${params[0].name}</strong><br/>`;
                            params.forEach(p => {
                                res += `${p.marker} ${p.seriesName}: <b>${formatNumber(p.value)}</b><br/>`;
                            });
                            return res;
                        }
                    },
                    legend: { data: ['PA', 'SV'], bottom: 0, textStyle: { color: '#fff', fontSize: 10 } },
                    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
                    xAxis: { type: 'category', data: charts.by_estado.map(d => d.Estado || 'N/A'), axisLabel: { rotate: 30, fontSize: 10, color: '#fff' } },
                    yAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { opacity: 0.1 } } },
                    series: [
                        {
                            name: 'PA',
                            type: 'bar',
                            data: charts.by_estado.map(d => d.pa),
                            itemStyle: { color: '#ff133f' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#ff133f',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        },
                        {
                            name: 'SV',
                            type: 'bar',
                            data: charts.by_estado.map(d => d.sv),
                            itemStyle: { color: '#00cfdc' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#00cfdc',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        }
                    ]
                });
            }

            // Gráfico Clientes (Horizontal Bar)
            chartsInstances.clientes = echarts.init(document.getElementById('chart-clientes'));
            if (charts.by_cliente_top10?.length > 0) {
                chartsInstances.clientes.setOption({
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (params) {
                            let res = `<strong>${params[0].name}</strong><br/>`;
                            params.forEach(p => {
                                res += `${p.marker} ${p.seriesName}: <b>${formatNumber(p.value)}</b><br/>`;
                            });
                            return res;
                        }
                    },
                    legend: { data: ['PA', 'SV'], bottom: 0, textStyle: { color: '#fff', fontSize: 10 } },
                    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
                    xAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { opacity: 0.1 } } },
                    yAxis: { type: 'category', data: charts.by_cliente_top10.map(d => (d.nombre || '').substring(0, 25)), inverse: true, axisLabel: { fontSize: 10, color: '#fff' } },
                    series: [
                        {
                            name: 'PA',
                            type: 'bar',
                            data: charts.by_cliente_top10.map(d => d.pa),
                            itemStyle: { color: '#ff133f' },
                            label: {
                                show: true,
                                position: 'right',
                                color: '#ff133f',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        },
                        {
                            name: 'SV',
                            type: 'bar',
                            data: charts.by_cliente_top10.map(d => d.sv),
                            itemStyle: { color: '#00cfdc' },
                            label: {
                                show: true,
                                position: 'right',
                                color: '#00cfdc',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        }
                    ]
                });
            }

            // Gráfico Zona (Bar)
            chartsInstances.zona = echarts.init(document.getElementById('chart-zona'));
            if (charts.by_zona?.length > 0) {
                chartsInstances.zona.setOption({
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (params) {
                            let res = `<strong>${params[0].name}</strong><br/>`;
                            params.forEach(p => {
                                res += `${p.marker} ${p.seriesName}: <b>${formatNumber(p.value)}</b><br/>`;
                            });
                            return res;
                        }
                    },
                    legend: { data: ['PA', 'SV'], bottom: 0, textStyle: { color: '#fff', fontSize: 10 } },
                    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
                    xAxis: {
                        type: 'category', data: charts.by_zona.map(d => d.Zona_Display || 'Sin Zona'), axisLabel: {
                            rotate: 45,
                            fontSize: 10,
                            color: '#fff'
                        }
                    },
                    yAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { opacity: 0.1 } } },
                    series: [
                        {
                            name: 'PA',
                            type: 'bar',
                            data: charts.by_zona.map(d => d.pa),
                            itemStyle: { color: '#ff2a57' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#ff2a57',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        },
                        {
                            name: 'SV',
                            type: 'bar',
                            data: charts.by_zona.map(d => d.sv),
                            itemStyle: { color: '#00cfdc' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#00cfdc',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        }
                    ]
                });
            } else {
                chartsInstances.zona.setOption({ title: { text: 'Sin datos de zona', left: 'center', top: 'center', textStyle: { color: '#999' } } });
            }

            // Gráfico MacroZona (Pie)
            chartsInstances.macrozona = echarts.init(document.getElementById('chart-macrozona'));
            if (charts.by_macrozona?.length > 0) {
                chartsInstances.macrozona.setOption({
                    tooltip: {
                        trigger: 'item',
                        formatter: function (params) {
                            let val = typeof params.value === 'number' ? params.value.toFixed(2) : params.value;
                            return `${params.name}: ${val} (${params.percent}%)`;
                        }
                    },
                    legend: {
                        orient: 'vertical',
                        left: 'left',
                        top: 'center',
                        textStyle: {
                            fontSize: 10,
                            color: '#fff'
                        }
                    },
                    series: [{
                        type: 'pie',
                        radius: ['30%', '60%'],
                        center: ['60%', '50%'],
                        data: charts.by_macrozona.map(d => ({ value: d.pa, name: d.Macrozona_SV || 'N/A' })),
                        label: { show: true, formatter: '{d}%', color: '#fff', fontWeight: 700 },
                    }]
                });
            } else {
                chartsInstances.macrozona.setOption({ title: { text: 'Sin datos de macrozona', left: 'center', top: 'center', textStyle: { color: '#999' } } });
            }

            // Gráfico Donut PA vs SV
            chartsInstances.donut = echarts.init(document.getElementById('chart-donut'));
            chartsInstances.donut.setOption({
                tooltip: {
                    trigger: 'item',
                    formatter: function (params) {
                        return `${params.name}: <b>${formatNumber(params.value)}</b> (${params.percent}%)`;
                    }
                },
                legend: { bottom: 0, textStyle: { color: '#fff', fontSize: 10 } },
                series: [{
                    type: 'pie',
                    radius: ['40%', '70%'],
                    avoidLabelOverlap: false,
                    label: { show: true, formatter: (p) => `${p.name}\n${formatNumber(p.value)} (${p.percent}%)`, color: '#fff', fontWeight: 700 },
                    data: [
                        { value: kpis.total_personal_asignado, name: 'Personal Asignado', itemStyle: { color: '#ff133f' } },
                        { value: kpis.total_servicio_vivo, name: 'Servicio Vivo', itemStyle: { color: '#00cfdc' } }
                    ]
                }]
            });

            // Gráfico Grupo
            chartsInstances.grupo = echarts.init(document.getElementById('chart-grupo'));
            if (charts.by_grupo?.length > 0) {
                const grupoKey = Object.keys(charts.by_grupo[0]).find(k => k.includes('Grupo'));
                chartsInstances.grupo.setOption({
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (params) {
                            let res = `<strong>${params[0].name}</strong><br/>`;
                            params.forEach(p => {
                                res += `${p.marker} ${p.seriesName}: <b>${formatNumber(p.value)}</b><br/>`;
                            });
                            return res;
                        }
                    },
                    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
                    xAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { opacity: 0.1 } } },
                    yAxis: { type: 'category', data: charts.by_grupo.map(d => (d[grupoKey] || '').substring(0, 20)), inverse: true, axisLabel: { color: '#fff', fontSize: 10 } },
                    series: [
                        {
                            name: 'PA',
                            type: 'bar',
                            stack: 'total',
                            data: charts.by_grupo.map(d => d.pa),
                            itemStyle: { color: '#ff133f' },
                            label: {
                                show: true,
                                position: 'right',
                                color: '#ff133f',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        },
                        {
                            name: 'SV',
                            type: 'bar',
                            stack: 'total',
                            data: charts.by_grupo.map(d => d.sv),
                            itemStyle: { color: '#00cfdc' },
                            label: {
                                show: true,
                                position: 'right',
                                color: '#00cfdc',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        }

                    ]
                });
            }

            // Gráfico Unidades Bar
            chartsInstances.unidadesBar = echarts.init(document.getElementById('chart-unidades-bar'));
            if (charts.by_unidad_top10?.length > 0) {
                chartsInstances.unidadesBar.setOption({
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (params) {
                            let res = `<strong>${params[0].name}</strong><br/>`;
                            params.forEach(p => {
                                res += `${p.marker} ${p.seriesName}: <b>${formatNumber(p.value)}</b><br/>`;
                            });
                            return res;
                        }
                    },
                    legend: { data: ['PA', 'SV'], bottom: 0, textStyle: { color: '#fff', fontSize: 10 } },
                    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
                    xAxis: { type: 'category', data: charts.by_unidad_top10.map(d => (d.nombre || d.Unidad_Str || '').substring(0, 20)), axisLabel: { rotate: 45, fontSize: 10, color: '#fff' } },
                    yAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { opacity: 0.1 } } },
                    series: [
                        {
                            name: 'PA',
                            type: 'bar',
                            data: charts.by_unidad_top10.map(d => d.pa),
                            itemStyle: { color: '#ff133f' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#ff133f',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        },
                        {
                            name: 'SV',
                            type: 'bar',
                            data: charts.by_unidad_top10.map(d => d.sv),
                            itemStyle: { color: '#00cfdc' },
                            label: {
                                show: true,
                                position: 'top',
                                color: '#00cfdc',
                                fontWeight: 700,
                                formatter: (p) => formatNumber(p.value)
                            }
                        }
                    ]
                });
            }

            // Responsive
            window.addEventListener('resize', () => {
                Object.values(chartsInstances).forEach(chart => chart && chart.resize());
            });
        }

        // ===== CARGAR DATOS PAGINADOS DE CLIENTES =====
        async function loadClientData() {
            const search = document.getElementById('search-cliente')?.value || '';
            try {
                const url = await buildApiUrl(`/dashboard/api/clients/?tenant=default&period=${currentPeriod}&page=${clientPage}&per_page=${perPage}&search=${encodeURIComponent(search)}`);
                const response = await fetch(url);
                const data = await response.json();

                renderClientTable(data);
                updateClientPagination(data);
            } catch (err) {
                console.error('Error cargando datos de clientes:', err);
            }
        }

        function renderClientTable(data) {
            const tbody = document.getElementById('table-clientes');
            if (!data.data?.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-500">Sin datos</td></tr>';
                updateClientTotals([]);
                return;
            }

            tbody.innerHTML = data.data.map(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                const cob = sv > 0 ? ((pa / sv) * 100).toFixed(2) : 'Infinito';
                const pct = sv > 0 ? ((diff / sv) * 100).toFixed(2) : 'Infinito';
                const estado = getEstadoFromDiff(pa, sv);
                return `<tr class="hover:bg-gray-50">
                    <td class="px-4 py-2 text-sm">${row.nombre || row.Cliente_Final || '-'}</td>
                    <td class="px-4 py-2 text-sm text-gray-500">-</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                    <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                    <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                    <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                </tr>`;
            }).join('');

            updateClientTotals(data.data);

            // Enforce table header styles after rendering
            setTimeout(enforceTableHeaderStyles, 10);
        }

        function updateClientTotals(data) {
            let totalPa = 0, totalSv = 0, totalDiff = 0;
            data.forEach(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                totalPa += pa;
                totalSv += sv;
                totalDiff += diff;
            });

            document.getElementById('total-pa-cli').textContent = formatNumber(totalPa);
            document.getElementById('total-sv-cli').textContent = formatNumber(totalSv);
            document.getElementById('total-diff-cli').textContent = formatNumber(totalDiff);
            document.getElementById('total-cob-cli').textContent = totalSv > 0 ? (totalPa / totalSv * 100).toFixed(2) + '%' : '-';
            document.getElementById('total-pct-cli').textContent = totalSv > 0 ? (totalDiff / totalSv * 100).toFixed(2) + '%' : '-';
        }

        function updateClientPagination(data) {
            const start = (data.page - 1) * data.per_page + 1;
            const end = Math.min(data.page * data.per_page, data.total);

            document.getElementById('page-start-clientes').textContent = data.total > 0 ? start : 0;
            document.getElementById('page-end-clientes').textContent = end;
            document.getElementById('total-records-clientes').textContent = data.total;
            document.getElementById('page-info-clientes').textContent = `${data.page}/${data.total_pages || 1}`;

            document.getElementById('prev-page-clientes').disabled = data.page <= 1;
            document.getElementById('next-page-clientes').disabled = data.page >= data.total_pages;
        }

        // ===== CARGAR DATOS PAGINADOS DE UNIDADES =====
        async function loadUnitData() {
            const search = document.getElementById('search-unidad')?.value || '';
            try {
                const url = await buildApiUrl(`/dashboard/api/units/?tenant=default&period=${currentPeriod}&page=${unitPage}&per_page=${perPage}&search=${encodeURIComponent(search)}`);
                const response = await fetch(url);
                const data = await response.json();

                renderUnitTable(data);
                updateUnitPagination(data);
            } catch (err) {
                console.error('Error cargando datos de unidades:', err);
            }
        }

        function renderUnitTable(data) {
            const tbody = document.getElementById('table-unidades');
            if (!data.data?.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Sin datos</td></tr>';
                updateUnitTotals([]);
                return;
            }

            tbody.innerHTML = data.data.map(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                const cob = sv > 0 ? (pa / sv * 100).toFixed(2) : 'Infinito';
                const pct = sv > 0 ? (diff / sv * 100).toFixed(2) : 'Infinito';
                const estado = getEstadoFromDiff(pa, sv);
                return `<tr class="hover:bg-gray-50">
                    <td class="px-4 py-2 text-sm">${row.nombre || row.Unidad_Str || '-'}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                    <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                    <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                    <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                </tr>`;
            }).join('');

            updateUnitTotals(data.data);

            // Enforce table header styles after rendering
            setTimeout(enforceTableHeaderStyles, 10);
        }

        function updateUnitTotals(data) {
            let totalPa = 0, totalSv = 0, totalDiff = 0;
            data.forEach(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                totalPa += pa;
                totalSv += sv;
                totalDiff += diff;
            });

            document.getElementById('total-pa-uni').textContent = formatNumber(totalPa);
            document.getElementById('total-sv-uni').textContent = formatNumber(totalSv);
            document.getElementById('total-diff-uni').textContent = formatNumber(totalDiff);
            document.getElementById('total-cob-uni').textContent = totalSv > 0 ? (totalPa / totalSv * 100).toFixed(2) + '%' : '-';
            document.getElementById('total-pct-uni').textContent = totalSv > 0 ? (totalDiff / totalSv * 100).toFixed(2) + '%' : '-';
        }

        function updateUnitPagination(data) {
            const start = (data.page - 1) * data.per_page + 1;
            const end = Math.min(data.page * data.per_page, data.total);

            document.getElementById('page-start-unidades').textContent = data.total > 0 ? start : 0;
            document.getElementById('page-end-unidades').textContent = end;
            document.getElementById('total-records-unidades').textContent = data.total;
            document.getElementById('page-info-unidades').textContent = `${data.page}/${data.total_pages || 1}`;

            document.getElementById('prev-page-unidades').disabled = data.page <= 1;
            document.getElementById('next-page-unidades').disabled = data.page >= data.total_pages;
        }

        // ===== CARGAR DATOS PAGINADOS DE SERVICIOS =====
        async function loadServiceData() {
            const search = document.getElementById('search-servicio')?.value || '';
            try {
                const url = await buildApiUrl(`/dashboard/api/services/?tenant=default&period=${currentPeriod}&page=${servicePage}&per_page=${perPage}&search=${encodeURIComponent(search)}`);
                const response = await fetch(url);
                const data = await response.json();

                renderServiceTable(data);
                updateServicePagination(data);
            } catch (err) {
                console.error('Error cargando datos de servicios:', err);
            }
        }

        function renderServiceTable(data) {
            const tbody = document.getElementById('table-servicios');
            if (!data.data?.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Sin datos</td></tr>';
                updateServiceTotals([]);
                return;
            }

            tbody.innerHTML = data.data.map(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                const cob = sv > 0 ? ((pa / sv) * 100).toFixed(2) : 'Infinito';
                const pct = sv > 0 ? ((diff / sv) * 100).toFixed(2) : 'Infinito';
                const estado = getEstadoFromDiff(pa, sv);
                return `<tr class="hover:bg-gray-50">
                    <td class="px-4 py-2 text-sm">${row.nombre || row.Servicio_Limpio || '-'}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                    <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                    <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                    <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                    <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                </tr>`;
            }).join('');

            updateServiceTotals(data.data);

            // Enforce table header styles after rendering
            setTimeout(enforceTableHeaderStyles, 10);
        }

        function updateServiceTotals(data) {
            let totalPa = 0, totalSv = 0, totalDiff = 0;
            data.forEach(row => {
                const pa = row.pa || 0;
                const sv = row.sv || 0;
                const diff = row.diferencia || (pa - sv);
                totalPa += pa;
                totalSv += sv;
                totalDiff += diff;
            });

            document.getElementById('total-pa-srv').textContent = formatNumber(totalPa);
            document.getElementById('total-sv-srv').textContent = formatNumber(totalSv);
            document.getElementById('total-diff-srv').textContent = formatNumber(totalDiff);
            document.getElementById('total-cob-srv').textContent = totalSv > 0 ? (totalPa / totalSv * 100).toFixed(2) + '%' : '-';
            document.getElementById('total-pct-srv').textContent = totalSv > 0 ? (totalDiff / totalSv * 100).toFixed(2) + '%' : '-';
        }

        function updateServicePagination(data) {
            const start = (data.page - 1) * data.per_page + 1;
            const end = Math.min(data.page * data.per_page, data.total);

            document.getElementById('page-start-servicios').textContent = data.total > 0 ? start : 0;
            document.getElementById('page-end-servicios').textContent = end;
            document.getElementById('total-records-servicios').textContent = data.total;
            document.getElementById('page-info-servicios').textContent = `${data.page}/${data.total_pages || 1}`;

            document.getElementById('prev-page-servicios').disabled = data.page <= 1;
            document.getElementById('next-page-servicios').disabled = data.page >= data.total_pages;
        }

        // ===== FUNCIÓN AUXILIAR PARA CONSTRUIR URLs CON FILTROS GLOBALES =====
        async function buildApiUrl(baseUrl) {
            const params = new URLSearchParams();

            // Agregar filtros globales
            const macrozona = document.getElementById('filter-macrozona').value;
            const zona = document.getElementById('filter-zona').value;
            const compania = document.getElementById('filter-compania').value;
            const grupo = document.getElementById('filter-grupo').value;
            const sector = document.getElementById('filter-sector').value;
            const gerente = document.getElementById('filter-gerente').value;

            if (macrozona) params.append('macrozona', macrozona);
            if (zona) params.append('zona', zona);
            if (compania) params.append('compania', compania);
            if (grupo) params.append('grupo', grupo);
            if (sector) params.append('sector', sector);
            if (gerente) params.append('gerente', gerente);

            const queryString = params.toString();
            return queryString ? `${baseUrl}&${queryString}` : baseUrl;
        }

        // ===== ACTUALIZAR TABLAS DE RESUMEN =====
        function updateTables(charts) {
            // Tabla Clientes
            const searchCliente = document.getElementById('search-cliente')?.value || '';
            if (charts.by_cliente_top10?.length > 0) {
                const tbody = document.getElementById('table-clientes');
                let totalPa = 0, totalSv = 0, totalDiff = 0;
                const filtered = charts.by_cliente_top10.filter(row => {
                    const nombre = (row.nombre || row.Cliente_Final || '').toLowerCase();
                    return nombre.includes(searchCliente.toLowerCase());
                });
                tbody.innerHTML = filtered.length > 0 ? filtered.map(row => {
                    const pa = row.pa || 0;
                    const sv = row.sv || 0;
                    const diff = row.diferencia || (pa - sv);
                    const cob = sv > 0 ? ((pa / sv) * 100).toFixed(2) : 'Infinito';
                    const pct = sv > 0 ? ((diff / sv) * 100).toFixed(2) : 'Infinito';
                    const estado = getEstadoFromDiff(pa, sv);
                    totalPa += pa;
                    totalSv += sv;
                    totalDiff += diff;
                    return `<tr class="hover:bg-gray-50">
                        <td class="px-4 py-2 text-sm">${row.nombre || row.Cliente_Final || '-'}</td>
                        <td class="px-4 py-2 text-sm text-gray-500">-</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                        <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                        <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                        <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                    </tr>`;
                }).join('') : `<tr><td colspan="8" class="px-4 py-8 text-center text-gray-500">Sin resultados</td></tr>`;
                document.getElementById('total-pa-cli').textContent = formatNumber(totalPa);
                document.getElementById('total-sv-cli').textContent = formatNumber(totalSv);
                document.getElementById('total-diff-cli').textContent = formatNumber(totalDiff);
                document.getElementById('total-cob-cli').textContent = totalSv > 0 ? ((totalPa / totalSv) * 100).toFixed(2) + '%' : '-';
                document.getElementById('total-pct-cli').textContent = totalSv > 0 ? ((totalDiff / totalSv) * 100).toFixed(2) + '%' : '-';
            }
            // Tabla Unidades
            const searchUnidad = document.getElementById('search-unidad')?.value || '';
            if (charts.by_unidad_top10?.length > 0) {
                const tbody = document.getElementById('table-unidades');
                let totalPa = 0, totalSv = 0, totalDiff = 0;
                const filtered = charts.by_unidad_top10.filter(row => {
                    const nombre = (row.nombre || row.Unidad_Str || '').toLowerCase();
                    return nombre.includes(searchUnidad.toLowerCase());
                });
                tbody.innerHTML = filtered.length > 0 ? filtered.map(row => {
                    const pa = row.pa || 0;
                    const sv = row.sv || 0;
                    const diff = row.diferencia || (pa - sv);
                    const cob = sv > 0 ? ((pa / sv) * 100).toFixed(2) : 'Infinito';
                    const pct = sv > 0 ? ((diff / sv) * 100).toFixed(2) : 'Infinito';
                    const estado = getEstadoFromDiff(pa, sv);
                    totalPa += pa;
                    totalSv += sv;
                    totalDiff += diff;
                    return `<tr class="hover:bg-gray-50">
                        <td class="px-4 py-2 text-sm">${row.nombre || row.Unidad_Str || '-'}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                        <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                        <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                        <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                    </tr>`;
                }).join('') : `<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Sin resultados</td></tr>`;
                document.getElementById('total-pa-uni').textContent = formatNumber(totalPa);
                document.getElementById('total-sv-uni').textContent = formatNumber(totalSv);
                document.getElementById('total-diff-uni').textContent = formatNumber(totalDiff);
                document.getElementById('total-cob-uni').textContent = totalSv > 0 ? ((totalPa / totalSv) * 100).toFixed(2) + '%' : '-';
                document.getElementById('total-pct-uni').textContent = totalSv > 0 ? ((totalDiff / totalSv) * 100).toFixed(2) + '%' : '-';
            }
            // Tabla Servicios
            const searchServicio = document.getElementById('search-servicio')?.value || '';
            if (charts.by_servicio_top10?.length > 0) {
                const tbody = document.getElementById('table-servicios');
                let totalPa = 0, totalSv = 0, totalDiff = 0;
                const filtered = charts.by_servicio_top10.filter(row => {
                    const nombre = (row.nombre || row.Servicio_Limpio || '').toLowerCase();
                    return nombre.includes(searchServicio.toLowerCase());
                });
                tbody.innerHTML = filtered.length > 0 ? filtered.map(row => {
                    const pa = row.pa || 0;
                    const sv = row.sv || 0;
                    const diff = row.diferencia || (pa - sv);
                    const cob = sv > 0 ? ((pa / sv) * 100).toFixed(2) : 'Infinito';
                    const pct = sv > 0 ? ((diff / sv) * 100).toFixed(2) : 'Infinito';
                    const estado = getEstadoFromDiff(pa, sv);
                    totalPa += pa;
                    totalSv += sv;
                    totalDiff += diff;
                    return `<tr class="hover:bg-gray-50">
                        <td class="px-4 py-2 text-sm">${row.nombre || row.Servicio_Limpio || '-'}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-blue-600">${formatNumber(pa)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium text-green-600">${formatNumber(sv)}</td>
                        <td class="px-4 py-2 text-sm text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                        <td class="px-4 py-2 text-sm text-right">${cob}%</td>
                        <td class="px-4 py-2 text-sm text-right">${pct}%</td>
                        <td class="px-4 py-2 text-center"><span class="status-badge estado-${estado}">${estado}</span></td>
                    </tr>`;
                }).join('') : `<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Sin resultados</td></tr>`;
                document.getElementById('total-pa-srv').textContent = formatNumber(totalPa);
                document.getElementById('total-sv-srv').textContent = formatNumber(totalSv);
                document.getElementById('total-diff-srv').textContent = formatNumber(totalDiff);
                document.getElementById('total-cob-srv').textContent = totalSv > 0 ? ((totalPa / totalSv) * 100).toFixed(2) + '%' : '-';
                document.getElementById('total-pct-srv').textContent = totalSv > 0 ? ((totalDiff / totalSv) * 100).toFixed(2) + '%' : '-';
            }

            // Enforce table header styles after rendering
            setTimeout(enforceTableHeaderStyles, 10);
        }
        // ===== BÚSQUEDA CON PAGINACIÓN =====
        // Listeners para inputs de búsqueda con debounce
        document.addEventListener('DOMContentLoaded', () => {
            let searchTimeout;

            const searchCliente = document.getElementById('search-cliente');
            if (searchCliente) {
                searchCliente.addEventListener('input', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        clientPage = 1;
                        loadClientData();
                    }, 300);
                });
            }

            const searchUnidad = document.getElementById('search-unidad');
            if (searchUnidad) {
                searchUnidad.addEventListener('input', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        unitPage = 1;
                        loadUnitData();
                    }, 300);
                });
            }

            const searchServicio = document.getElementById('search-servicio');
            if (searchServicio) {
                searchServicio.addEventListener('input', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        servicePage = 1;
                        loadServiceData();
                    }, 300);
                });
            }
        });

        // ===== CARGAR DATOS DE TABLA DETALLE =====
        async function loadTableData() {
            const search = document.getElementById('search-input').value;
            try {
                // Usar buildApiUrl para incluir filtros globales
                const baseUrl = `/dashboard/api/details/?tenant=default&period=${currentPeriod}&page=${currentPage}&per_page=25&search=${encodeURIComponent(search)}&sort_by=${sortBy}&sort_order=${sortOrder}`;
                const url = await buildApiUrl(baseUrl);
                const response = await fetch(url);
                const data = await response.json();

                renderDetailTable(data);
                updatePagination(data);
            } catch (err) {
                console.error('Error cargando tabla:', err);
            }
        }

        function renderDetailTable(data) {
            const tbody = document.getElementById('table-body');
            if (!data.data?.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="px-3 py-8 text-center text-gray-500">Sin datos</td></tr>';
                return;
            }

            tbody.innerHTML = data.data.map(row => {
                const diff = row.Personal_Estimado - row.Personal_Real;
                return `<tr class="hover:bg-gray-50">
                    <td class="px-3 py-2 truncate max-w-[200px]">${row.Cliente_Final || '-'}</td>
                    <td class="px-3 py-2 truncate max-w-[150px]">${row.Unidad_Str || '-'}</td>
                    <td class="px-3 py-2 truncate max-w-[150px]">${row.Servicio_Limpio || '-'}</td>
                    <td class="px-3 py-2 text-right font-medium text-blue-600">${formatNumber(row.Personal_Real || 0)}</td>
                    <td class="px-3 py-2 text-right font-medium text-green-600">${formatNumber(row.Personal_Estimado || 0)}</td>
                    <td class="px-3 py-2 text-right font-medium ${diff >= 0 ? 'text-orange-600' : 'text-red-600'}">${formatNumber(diff)}</td>
                    <td class="px-3 py-2 text-center"><span class="status-badge estado-${row.Estado}">${row.Estado || '-'}</span></td>
                </tr>`;
            }).join('');

            // Enforce table header styles after rendering
            setTimeout(enforceTableHeaderStyles, 10);
        }

        function updatePagination(data) {
            const start = (data.page - 1) * data.per_page + 1;
            const end = Math.min(data.page * data.per_page, data.total);

            document.getElementById('page-start').textContent = data.total > 0 ? start : 0;
            document.getElementById('page-end').textContent = end;
            document.getElementById('total-records').textContent = data.total;
            document.getElementById('page-info').textContent = `${data.page}/${data.total_pages || 1}`;

            document.getElementById('prev-page').disabled = data.page <= 1;
            document.getElementById('next-page').disabled = data.page >= data.total_pages;
        }

        // ===== EVENT LISTENERS =====
        function setupEventListeners() {
            // Periodo
            document.getElementById('period-select').addEventListener('change', e => {
                currentPeriod = e.target.value;
                currentPage = 1;
                clientPage = 1;
                unitPage = 1;
                servicePage = 1;
                loadMetrics(currentPeriod);
            });

            // Búsqueda con debounce
            let searchTimeout;
            document.getElementById('search-input').addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => { currentPage = 1; loadTableData(); }, 300);
            });

            // Ordenar columnas
            document.querySelectorAll('th[data-sort]').forEach(th => {
                th.addEventListener('click', () => {
                    const col = th.dataset.sort;
                    sortOrder = sortBy === col ? (sortOrder === 'asc' ? 'desc' : 'asc') : 'desc';
                    sortBy = col;
                    loadTableData();
                });
            });

            // Paginación Detalle
            document.getElementById('prev-page').addEventListener('click', () => { if (currentPage > 1) { currentPage--; loadTableData(); } });
            document.getElementById('next-page').addEventListener('click', () => { currentPage++; loadTableData(); });

            // Paginación Clientes
            document.getElementById('prev-page-clientes').addEventListener('click', () => {
                if (clientPage > 1) {
                    clientPage--;
                    loadClientData();
                }
            });
            document.getElementById('next-page-clientes').addEventListener('click', () => {
                clientPage++;
                loadClientData();
            });

            // Paginación Unidades
            document.getElementById('prev-page-unidades').addEventListener('click', () => {
                if (unitPage > 1) {
                    unitPage--;
                    loadUnitData();
                }
            });
            document.getElementById('next-page-unidades').addEventListener('click', () => {
                unitPage++;
                loadUnitData();
            });

            // Paginación Servicios
            document.getElementById('prev-page-servicios').addEventListener('click', () => {
                if (servicePage > 1) {
                    servicePage--;
                    loadServiceData();
                }
            });
            document.getElementById('next-page-servicios').addEventListener('click', () => {
                servicePage++;
                loadServiceData();
            });

            // Modal comparación
            document.getElementById('compare-btn').addEventListener('click', () => document.getElementById('compare-modal').classList.remove('hidden'));
            document.getElementById('close-modal').addEventListener('click', () => document.getElementById('compare-modal').classList.add('hidden'));
            document.getElementById('run-compare').addEventListener('click', runComparison);

            // Exportar
            document.getElementById('export-btn').addEventListener('click', () => window.open('/api/v1/jobs/latest/download/?tenant=default', '_blank'));

            // Limpiar filtros
            document.getElementById('clear-filters').addEventListener('click', () => {
                document.querySelectorAll('.filter-select').forEach(s => s.selectedIndex = 0);
                // Reset pagination
                clientPage = 1;
                unitPage = 1;
                servicePage = 1;
                currentPage = 1;
                loadMetrics(currentPeriod);  // Recargar sin filtros

                // Si estamos en el tab de detalle, recargar tabla de detalle
                const activeTab = document.querySelector('.tab-btn.tab-active');
                if (activeTab && activeTab.dataset.tab === 'detalle') {
                    loadTableData();
                }
            });

            // Event listeners para filtros - recargar datos cuando cambian
            document.querySelectorAll('.filter-select').forEach(select => {
                select.addEventListener('change', () => {
                    loadMetrics(currentPeriod);
                    // Reset pagination when filters change
                    clientPage = 1;
                    unitPage = 1;
                    servicePage = 1;
                    currentPage = 1;

                    // Si estamos en el tab de detalle, recargar tabla de detalle
                    const activeTab = document.querySelector('.tab-btn.tab-active');
                    if (activeTab && activeTab.dataset.tab === 'detalle') {
                        loadTableData();
                    }
                });
            });
        }

        // ===== COMPARACIÓN =====
        async function runComparison() {
            const p2 = document.getElementById('compare-period2').value;

            // Función para formatear fechas en español
            const formatDateSpanish = (dateStr) => {
                if (!dateStr) return dateStr;
                try {
                    // Intentar detectar si es una fecha (ej: 2024-12-31)
                    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                        const [y, m, d] = dateStr.split('-');
                        const date = new Date(y, m - 1, d);
                        return new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' }).format(date);
                    }
                    return dateStr;
                } catch (e) {
                    return dateStr;
                }
            };

            try {
                const response = await fetch(`/dashboard/api/compare/?tenant=default&period1=${p1}&period2=${p2}`);
                const data = await response.json();

                if (data.error) { alert(data.error); return; }

                const tableDiv = document.getElementById('compare-table');
                tableDiv.innerHTML = Object.entries(data.comparison).map(([key, val]) => `
                    <div class="flex justify-between items-center p-2 bg-gray-50 rounded text-sm">
                        <span class="font-medium">${formatMetricName(key)}</span>
                        <div class="text-right">
                            <span class="text-gray-600">${formatNumber(val.previous)} → ${formatNumber(val.current)}</span>
                            <span class="ml-2 ${val.diff >= 0 ? 'text-green-600' : 'text-red-600'}">
                                (${val.diff >= 0 ? '+' : ''}${formatNumber(val.diff)}, ${val.pct_change}%)
                            </span>
                        </div>
                    </div>
                `).join('');

                document.getElementById('compare-results').classList.remove('hidden');
            } catch (err) {
                console.error('Error:', err);
            }
        }

        // ===== UTILIDADES =====
        const formatDateSpanish = (dateStr) => {
            if (!dateStr) return dateStr;
            try {
                // Si es un string de fecha ISO (YYYY-MM-DD)
                if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                    const [y, m, d] = dateStr.split('-');
                    const date = new Date(y, m - 1, d);
                    return new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' }).format(date);
                }
                return dateStr;
            } catch (e) {
                return dateStr;
            }
        };

        function showLoading(show) { document.getElementById('loading').classList.toggle('hidden', !show); }
        function showNoData() { document.querySelectorAll('[id^="kpi-"]').forEach(el => el.textContent = '--'); }
        function formatNumber(n) {
            if (n == null) return '-';
            return new Intl.NumberFormat('es-PE', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(n);
        }
        function formatMetricName(key) {
            const names = { 'total_personal_asignado': 'Personal Asignado', 'total_servicio_vivo': 'Servicio Vivo', 'coincidencias': 'Coincidencias', 'diferencia_total': 'Diferencia', 'cobertura_porcentaje': 'Cobertura %' };
            return names[key] || key;
        }
        function getEstadoFromDiff(pa, sv) {
            if (pa === 0 && sv === 0) return 'SIN_DATOS';
            if (pa === 0) return 'SIN_PERSONAL';
            if (sv === 0) return 'NO_PLANIFICADO';
            if (pa === sv) return 'EXACTO';
            if (pa > sv) return 'SOBRECARGA';
            return 'FALTA';
        }