export class ParamForm {
    constructor(containerId, onChange) {
        this.container = document.getElementById(containerId);
        this.onChange = onChange;
        this.values = {};
    }

    build(schema, currentValues) {
        this.container.innerHTML = '';
        this.values = { ...currentValues };

        schema.forEach(field => {
            const wrapper = document.createElement('div');
            wrapper.className = 'param-field';

            const label = document.createElement('label');
            label.textContent = field.label;
            wrapper.appendChild(label);

            if (field.type === 'number') {
                const row = document.createElement('div');
                row.className = 'slider-row';

                const slider = document.createElement('input');
                slider.type = 'range';
                slider.min = field.min;
                slider.max = field.max;
                slider.step = field.step || 1;
                slider.value = currentValues[field.key] ?? ((field.min + field.max) / 2);

                const valDisplay = document.createElement('span');
                valDisplay.className = 'slider-value';
                valDisplay.textContent = slider.value;

                slider.addEventListener('input', () => {
                    valDisplay.textContent = slider.value;
                    this.values[field.key] = parseFloat(slider.value);
                    if (this.onChange) this.onChange(field.key, this.values[field.key]);
                });

                row.appendChild(slider);
                row.appendChild(valDisplay);
                wrapper.appendChild(row);
            } else if (field.type === 'select') {
                const select = document.createElement('select');
                field.options.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt;
                    option.textContent = opt;
                    if (currentValues[field.key] === opt) option.selected = true;
                    select.appendChild(option);
                });
                select.addEventListener('change', () => {
                    this.values[field.key] = select.value;
                    if (this.onChange) this.onChange(field.key, select.value);
                });
                wrapper.appendChild(select);
            } else if (field.type === 'checkbox') {
                const lbl = document.createElement('label');
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = !!currentValues[field.key];
                cb.addEventListener('change', () => {
                    this.values[field.key] = cb.checked;
                    if (this.onChange) this.onChange(field.key, cb.checked);
                });
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(' ' + field.label));
                wrapper.innerHTML = '';
                wrapper.appendChild(lbl);
            }

            this.container.appendChild(wrapper);
        });
    }

    getValues() {
        return { ...this.values };
    }
}
