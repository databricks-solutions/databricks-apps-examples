/**
 * Custom AG Grid functions for Range Optimizer
 * 
 * NOTE: Cell styling now uses AG Grid's built-in styleConditions feature
 * (defined in Python column defs) instead of custom JS functions.
 */

var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

/**
 * Dynamic segment options based on the product's category
 * Returns cellEditorParams object with values array for the selected category
 */
dagfuncs.dynamicSegmentOptions = function(params) {
    const category = params.data ? params.data.CATEGORY : null;
    
    const segmentsByCategory = {
        "Beer & Seltzer": ["Craft Beer", "Hard Seltzer"],
        "Hot Sauce": ["Asian Style", "Louisiana Style", "Mexican Style"],
        "Ice Cream": ["Premium Pints", "Family Tubs"],
    };
    
    // Return values for the agSelectCellEditor
    const values = segmentsByCategory[category] || [
        "Craft Beer", "Hard Seltzer",
        "Asian Style", "Louisiana Style", "Mexican Style",
        "Premium Pints", "Family Tubs"
    ];
    
    // agSelectCellEditor expects {values: [...]}
    return { values: values };
};
