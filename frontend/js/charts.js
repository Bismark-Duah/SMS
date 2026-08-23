const SVG_NS = "http://www.w3.org/2000/svg";

function createBarChart(containerId, labels, data, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  container.innerHTML = '';
  
  const width = container.clientWidth || 500;
  const height = options.height || 220;
  const paddingLeft = 50;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;
  
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.style.overflow = "visible";
  
  // Gradients
  const defs = document.createElementNS(SVG_NS, "defs");
  const gradient = document.createElementNS(SVG_NS, "linearGradient");
  gradient.setAttribute("id", "barGradient");
  gradient.setAttribute("x1", "0%");
  gradient.setAttribute("y1", "0%");
  gradient.setAttribute("x2", "0%");
  gradient.setAttribute("y2", "100%");
  
  const stop1 = document.createElementNS(SVG_NS, "stop");
  stop1.setAttribute("offset", "0%");
  stop1.setAttribute("stop-color", "var(--secondary, #06b6d4)");
  
  const stop2 = document.createElementNS(SVG_NS, "stop");
  stop2.setAttribute("offset", "100%");
  stop2.setAttribute("stop-color", "var(--primary, #4f46e5)");
  
  gradient.appendChild(stop1);
  gradient.appendChild(stop2);
  defs.appendChild(gradient);
  svg.appendChild(defs);
  
  // Axis scales
  const maxVal = Math.max(...data, 100); // default max 100 for percentage/grades
  
  // Draw Grid Lines (Y-Axis ticks)
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const val = (maxVal / ticks) * i;
    const y = paddingTop + chartHeight - (chartHeight * (val / maxVal));
    
    // Grid line
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", paddingLeft);
    line.setAttribute("y1", y);
    line.setAttribute("x2", width - paddingRight);
    line.setAttribute("y2", y);
    line.setAttribute("stroke", "rgba(255,255,255,0.05)");
    line.setAttribute("stroke-dasharray", "4");
    svg.appendChild(line);
    
    // Label
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", paddingLeft - 10);
    text.setAttribute("y", y + 4);
    text.setAttribute("fill", "var(--text-secondary)");
    text.setAttribute("font-size", "10px");
    text.setAttribute("text-anchor", "end");
    text.textContent = Math.round(val);
    svg.appendChild(text);
  }
  
  // Draw Bars & X Labels
  const barSpacing = chartWidth / data.length;
  const barWidth = barSpacing * 0.6;
  
  data.forEach((val, idx) => {
    const x = paddingLeft + (idx * barSpacing) + (barSpacing - barWidth) / 2;
    const barHeight = chartHeight * (val / maxVal);
    const y = paddingTop + chartHeight - barHeight;
    
    // Create Bar Rect
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", barWidth);
    rect.setAttribute("height", barHeight);
    rect.setAttribute("rx", "4");
    rect.setAttribute("fill", "url(#barGradient)");
    rect.style.cursor = "pointer";
    rect.style.transition = "all 0.2s ease";
    
    // Tooltip / title
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${labels[idx]}: ${val}`;
    rect.appendChild(title);
    
    // Hover animation
    rect.addEventListener("mouseenter", () => {
      rect.setAttribute("opacity", "0.85");
    });
    rect.addEventListener("mouseleave", () => {
      rect.setAttribute("opacity", "1");
    });
    
    svg.appendChild(rect);
    
    // X axis labels
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", x + barWidth / 2);
    text.setAttribute("y", height - paddingBottom + 18);
    text.setAttribute("fill", "var(--text-secondary)");
    text.setAttribute("font-size", "10px");
    text.setAttribute("text-anchor", "middle");
    // truncate text if too long
    const labelText = labels[idx].length > 10 ? labels[idx].substring(0, 8) + ".." : labels[idx];
    text.textContent = labelText;
    svg.appendChild(text);
  });
  
  container.appendChild(svg);
}

function createLineChart(containerId, labels, data, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  container.innerHTML = '';
  
  const width = container.clientWidth || 500;
  const height = options.height || 220;
  const paddingLeft = 50;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;
  
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.style.overflow = "visible";
  
  const maxVal = Math.max(...data, 100);
  
  // Y-axis grid and ticks
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const val = (maxVal / ticks) * i;
    const y = paddingTop + chartHeight - (chartHeight * (val / maxVal));
    
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", paddingLeft);
    line.setAttribute("y1", y);
    line.setAttribute("x2", width - paddingRight);
    line.setAttribute("y2", y);
    line.setAttribute("stroke", "rgba(255,255,255,0.05)");
    line.setAttribute("stroke-dasharray", "4");
    svg.appendChild(line);
    
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", paddingLeft - 10);
    text.setAttribute("y", y + 4);
    text.setAttribute("fill", "var(--text-secondary)");
    text.setAttribute("font-size", "10px");
    text.setAttribute("text-anchor", "end");
    text.textContent = Math.round(val);
    svg.appendChild(text);
  }
  
  // Generate coordinates
  const step = data.length > 1 ? chartWidth / (data.length - 1) : chartWidth;
  const points = data.map((val, idx) => {
    const x = paddingLeft + (idx * step);
    const y = paddingTop + chartHeight - (chartHeight * (val / maxVal));
    return { x, y, val, label: labels[idx] };
  });
  
  if (points.length > 0) {
    // Draw Path Line
    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      pathD += ` L ${points[i].x} ${points[i].y}`;
    }
    
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", pathD);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "var(--secondary, #06b6d4)");
    path.setAttribute("stroke-width", "3");
    svg.appendChild(path);
    
    // Draw dots and tooltips
    points.forEach((pt) => {
      const circle = document.createElementNS(SVG_NS, "circle");
      circle.setAttribute("cx", pt.x);
      circle.setAttribute("cy", pt.y);
      circle.setAttribute("r", "5");
      circle.setAttribute("fill", "var(--primary, #4f46e5)");
      circle.setAttribute("stroke", "#fff");
      circle.setAttribute("stroke-width", "1.5");
      circle.style.cursor = "pointer";
      
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = `${pt.label}: ${pt.val}`;
      circle.appendChild(title);
      
      svg.appendChild(circle);
      
      // X labels
      const text = document.createElementNS(SVG_NS, "text");
      text.setAttribute("x", pt.x);
      text.setAttribute("y", height - paddingBottom + 18);
      text.setAttribute("fill", "var(--text-secondary)");
      text.setAttribute("font-size", "10px");
      text.setAttribute("text-anchor", "middle");
      text.textContent = pt.label;
      svg.appendChild(text);
    });
  }
  
  container.appendChild(svg);
}

window.createBarChart = createBarChart;
window.createLineChart = createLineChart;
