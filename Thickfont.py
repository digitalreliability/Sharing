from fontTools.ttLib import TTFont
from fontTools.misc.transform import Transform
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen  # ✅ import this

def thicken_font(input_path, output_path, thickness):
    """
    Increases the thickness of a font by scaling the glyph outlines.
    
    Args:
        input_path (str): The path to the input .ttf font file.
        output_path (str): The path to save the modified .ttf font file.
        thickness (int): The amount of thickness to add. A value of 50-100 is a good starting point.
    """
    try:
        font = TTFont(input_path)
        glyf_table = font['glyf']
        glyph_set = font.getGlyphSet()

        # Determine a scaling factor based on the UPM and desired thickness
        units_per_em = font['head'].unitsPerEm
        scale_factor = 1 + (thickness / units_per_em)

        for glyph_name in font.getGlyphOrder():
            glyf_object = glyf_table[glyph_name]   # Actual glyph object
            glyph_object = glyph_set[glyph_name]   # Drawable glyph

            if glyf_object.isComposite():
                # Scale composite glyph components
                for component in glyf_object.components:
                    t = component.transform
                    component.transform = (
                        t[0] * scale_factor, t[1], t[2],
                        t[3] * scale_factor, t[4], t[5]
                    )
            else:
                # For simple glyphs, apply scaling via TransformPen
                new_glyph_pen = TTGlyphPen(glyph_set)
                transform = Transform(scale_factor, 0, 0, scale_factor, 0, 0)
                tpen = TransformPen(new_glyph_pen, transform)  # ✅ wrap pen
                glyph_object.draw(tpen)
                glyf_table[glyph_name] = new_glyph_pen.glyph()

            # Recalculate bounds
            if hasattr(glyf_table[glyph_name], 'recalcBounds'):
                glyf_table[glyph_name].recalcBounds(glyph_set[glyph_name].width)

        font.save(output_path)
        print(f"✅ Successfully created a thicker font: {output_path}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")


# --- Example Usage ---
input_font_path = 'KishoreDvr-Regular.ttf'
output_font_path = 'KishoreDvr-Thicker.ttf'
thickness_value = 100 

thicken_font(input_font_path, output_font_path, thickness_value)
