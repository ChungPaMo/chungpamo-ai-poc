-- E05 SQLite 검증 질의 (scripts/e05_validate_sql.py가 생성). 규칙 ID는 configs/e05_validation_rules.json

-- S01 Unit.record_uid
SELECT record_uid, "record_uid" FROM "Unit" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Unit.origin_class
SELECT record_uid, "origin_class" FROM "Unit" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Unit.origin_class
SELECT record_uid, "origin_class" FROM "Unit" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Unit.unit_code
SELECT record_uid, "unit_code" FROM "Unit" WHERE "unit_code" IS NULL OR "unit_code" = '';

-- S01 Unit.dimension
SELECT record_uid, "dimension" FROM "Unit" WHERE "dimension" IS NULL OR "dimension" = '';

-- S04 Unit.dimension
SELECT record_uid, "dimension" FROM "Unit" WHERE "dimension" IS NOT NULL AND "dimension" <> '' AND "dimension" NOT IN ('MASS', 'COUNT', 'TIME');

-- S01 Unit.base_unit_code
SELECT record_uid, "base_unit_code" FROM "Unit" WHERE "base_unit_code" IS NULL OR "base_unit_code" = '';

-- S01 Unit.to_base_factor
SELECT record_uid, "to_base_factor" FROM "Unit" WHERE "to_base_factor" IS NULL OR "to_base_factor" = '';

-- S02 Unit.to_base_factor
SELECT record_uid, "to_base_factor" FROM "Unit" WHERE "to_base_factor" IS NOT NULL AND "to_base_factor" <> '' AND NOT ("to_base_factor" NOT GLOB '*[^0-9.-]*' AND "to_base_factor" GLOB '*[0-9]*' AND "to_base_factor" NOT GLOB '?*-*' AND (length("to_base_factor") - length(replace("to_base_factor", '.', ''))) <= 1);

-- S06 Unit.to_base_factor
SELECT record_uid, "to_base_factor" FROM "Unit" WHERE "to_base_factor" IS NOT NULL AND "to_base_factor" <> '' AND ("to_base_factor" NOT GLOB '*[^0-9.-]*' AND "to_base_factor" GLOB '*[0-9]*' AND "to_base_factor" NOT GLOB '?*-*' AND (length("to_base_factor") - length(replace("to_base_factor", '.', ''))) <= 1) AND (CAST("to_base_factor" AS REAL) <= 0);

-- S05 Unit.record_uid
SELECT record_uid, record_uid FROM "Unit" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Product.record_uid
SELECT record_uid, "record_uid" FROM "Product" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Product.origin_class
SELECT record_uid, "origin_class" FROM "Product" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Product.origin_class
SELECT record_uid, "origin_class" FROM "Product" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Product.product_id
SELECT record_uid, "product_id" FROM "Product" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 Product.product_name
SELECT record_uid, "product_name" FROM "Product" WHERE "product_name" IS NULL OR "product_name" = '';

-- S01 Product.product_type
SELECT record_uid, "product_type" FROM "Product" WHERE "product_type" IS NULL OR "product_type" = '';

-- S04 Product.product_type
SELECT record_uid, "product_type" FROM "Product" WHERE "product_type" IS NOT NULL AND "product_type" <> '' AND "product_type" NOT IN ('FINISHED', 'SEMI_FINISHED');

-- S01 Product.base_unit
SELECT record_uid, "base_unit" FROM "Product" WHERE "base_unit" IS NULL OR "base_unit" = '';

-- S01 Product.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Product" WHERE "safety_stock_qty" IS NULL OR "safety_stock_qty" = '';

-- S02 Product.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Product" WHERE "safety_stock_qty" IS NOT NULL AND "safety_stock_qty" <> '' AND NOT ("safety_stock_qty" NOT GLOB '*[^0-9.-]*' AND "safety_stock_qty" GLOB '*[0-9]*' AND "safety_stock_qty" NOT GLOB '?*-*' AND (length("safety_stock_qty") - length(replace("safety_stock_qty", '.', ''))) <= 1);

-- S06 Product.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Product" WHERE "safety_stock_qty" IS NOT NULL AND "safety_stock_qty" <> '' AND ("safety_stock_qty" NOT GLOB '*[^0-9.-]*' AND "safety_stock_qty" GLOB '*[0-9]*' AND "safety_stock_qty" NOT GLOB '?*-*' AND (length("safety_stock_qty") - length(replace("safety_stock_qty", '.', ''))) <= 1) AND (CAST("safety_stock_qty" AS REAL) < 0);

-- S01 Product.manuf_lead_time_days
SELECT record_uid, "manuf_lead_time_days" FROM "Product" WHERE "manuf_lead_time_days" IS NULL OR "manuf_lead_time_days" = '';

-- S02 Product.manuf_lead_time_days
SELECT record_uid, "manuf_lead_time_days" FROM "Product" WHERE "manuf_lead_time_days" IS NOT NULL AND "manuf_lead_time_days" <> '' AND NOT ("manuf_lead_time_days" NOT GLOB '*[^0-9-]*' AND "manuf_lead_time_days" GLOB '*[0-9]*' AND "manuf_lead_time_days" NOT GLOB '?*-*');

-- S06 Product.manuf_lead_time_days
SELECT record_uid, "manuf_lead_time_days" FROM "Product" WHERE "manuf_lead_time_days" IS NOT NULL AND "manuf_lead_time_days" <> '' AND ("manuf_lead_time_days" NOT GLOB '*[^0-9-]*' AND "manuf_lead_time_days" GLOB '*[0-9]*' AND "manuf_lead_time_days" NOT GLOB '?*-*') AND (CAST("manuf_lead_time_days" AS REAL) < 0);

-- S01 Product.outsourcing_allowed
SELECT record_uid, "outsourcing_allowed" FROM "Product" WHERE "outsourcing_allowed" IS NULL OR "outsourcing_allowed" = '';

-- S02 Product.outsourcing_allowed
SELECT record_uid, "outsourcing_allowed" FROM "Product" WHERE "outsourcing_allowed" IS NOT NULL AND "outsourcing_allowed" NOT IN (0, 1);

-- S07 Product.outsourcing_unit_cost
SELECT record_uid, "outsourcing_unit_cost" FROM "Product" WHERE "outsourcing_unit_cost" = '';

-- S02 Product.outsourcing_unit_cost
SELECT record_uid, "outsourcing_unit_cost" FROM "Product" WHERE "outsourcing_unit_cost" IS NOT NULL AND "outsourcing_unit_cost" <> '' AND NOT ("outsourcing_unit_cost" NOT GLOB '*[^0-9.-]*' AND "outsourcing_unit_cost" GLOB '*[0-9]*' AND "outsourcing_unit_cost" NOT GLOB '?*-*' AND (length("outsourcing_unit_cost") - length(replace("outsourcing_unit_cost", '.', ''))) <= 1);

-- S06 Product.outsourcing_unit_cost
SELECT record_uid, "outsourcing_unit_cost" FROM "Product" WHERE "outsourcing_unit_cost" IS NOT NULL AND "outsourcing_unit_cost" <> '' AND ("outsourcing_unit_cost" NOT GLOB '*[^0-9.-]*' AND "outsourcing_unit_cost" GLOB '*[0-9]*' AND "outsourcing_unit_cost" NOT GLOB '?*-*' AND (length("outsourcing_unit_cost") - length(replace("outsourcing_unit_cost", '.', ''))) <= 1) AND (CAST("outsourcing_unit_cost" AS REAL) < 0);

-- S05 Product.record_uid
SELECT record_uid, record_uid FROM "Product" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Material.record_uid
SELECT record_uid, "record_uid" FROM "Material" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Material.origin_class
SELECT record_uid, "origin_class" FROM "Material" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Material.origin_class
SELECT record_uid, "origin_class" FROM "Material" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Material.material_id
SELECT record_uid, "material_id" FROM "Material" WHERE "material_id" IS NULL OR "material_id" = '';

-- S01 Material.material_name
SELECT record_uid, "material_name" FROM "Material" WHERE "material_name" IS NULL OR "material_name" = '';

-- S01 Material.base_unit
SELECT record_uid, "base_unit" FROM "Material" WHERE "base_unit" IS NULL OR "base_unit" = '';

-- S01 Material.unit_cost
SELECT record_uid, "unit_cost" FROM "Material" WHERE "unit_cost" IS NULL OR "unit_cost" = '';

-- S02 Material.unit_cost
SELECT record_uid, "unit_cost" FROM "Material" WHERE "unit_cost" IS NOT NULL AND "unit_cost" <> '' AND NOT ("unit_cost" NOT GLOB '*[^0-9.-]*' AND "unit_cost" GLOB '*[0-9]*' AND "unit_cost" NOT GLOB '?*-*' AND (length("unit_cost") - length(replace("unit_cost", '.', ''))) <= 1);

-- S06 Material.unit_cost
SELECT record_uid, "unit_cost" FROM "Material" WHERE "unit_cost" IS NOT NULL AND "unit_cost" <> '' AND ("unit_cost" NOT GLOB '*[^0-9.-]*' AND "unit_cost" GLOB '*[0-9]*' AND "unit_cost" NOT GLOB '?*-*' AND (length("unit_cost") - length(replace("unit_cost", '.', ''))) <= 1) AND (CAST("unit_cost" AS REAL) < 0);

-- S01 Material.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Material" WHERE "safety_stock_qty" IS NULL OR "safety_stock_qty" = '';

-- S02 Material.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Material" WHERE "safety_stock_qty" IS NOT NULL AND "safety_stock_qty" <> '' AND NOT ("safety_stock_qty" NOT GLOB '*[^0-9.-]*' AND "safety_stock_qty" GLOB '*[0-9]*' AND "safety_stock_qty" NOT GLOB '?*-*' AND (length("safety_stock_qty") - length(replace("safety_stock_qty", '.', ''))) <= 1);

-- S06 Material.safety_stock_qty
SELECT record_uid, "safety_stock_qty" FROM "Material" WHERE "safety_stock_qty" IS NOT NULL AND "safety_stock_qty" <> '' AND ("safety_stock_qty" NOT GLOB '*[^0-9.-]*' AND "safety_stock_qty" GLOB '*[0-9]*' AND "safety_stock_qty" NOT GLOB '?*-*' AND (length("safety_stock_qty") - length(replace("safety_stock_qty", '.', ''))) <= 1) AND (CAST("safety_stock_qty" AS REAL) < 0);

-- S05 Material.record_uid
SELECT record_uid, record_uid FROM "Material" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Supplier.record_uid
SELECT record_uid, "record_uid" FROM "Supplier" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Supplier.origin_class
SELECT record_uid, "origin_class" FROM "Supplier" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Supplier.origin_class
SELECT record_uid, "origin_class" FROM "Supplier" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Supplier.supplier_id
SELECT record_uid, "supplier_id" FROM "Supplier" WHERE "supplier_id" IS NULL OR "supplier_id" = '';

-- S01 Supplier.supplier_name
SELECT record_uid, "supplier_name" FROM "Supplier" WHERE "supplier_name" IS NULL OR "supplier_name" = '';

-- S05 Supplier.record_uid
SELECT record_uid, record_uid FROM "Supplier" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 SupplierMaterial.record_uid
SELECT record_uid, "record_uid" FROM "SupplierMaterial" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 SupplierMaterial.origin_class
SELECT record_uid, "origin_class" FROM "SupplierMaterial" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 SupplierMaterial.origin_class
SELECT record_uid, "origin_class" FROM "SupplierMaterial" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 SupplierMaterial.supplier_id
SELECT record_uid, "supplier_id" FROM "SupplierMaterial" WHERE "supplier_id" IS NULL OR "supplier_id" = '';

-- S01 SupplierMaterial.material_id
SELECT record_uid, "material_id" FROM "SupplierMaterial" WHERE "material_id" IS NULL OR "material_id" = '';

-- S01 SupplierMaterial.lead_time_days
SELECT record_uid, "lead_time_days" FROM "SupplierMaterial" WHERE "lead_time_days" IS NULL OR "lead_time_days" = '';

-- S02 SupplierMaterial.lead_time_days
SELECT record_uid, "lead_time_days" FROM "SupplierMaterial" WHERE "lead_time_days" IS NOT NULL AND "lead_time_days" <> '' AND NOT ("lead_time_days" NOT GLOB '*[^0-9-]*' AND "lead_time_days" GLOB '*[0-9]*' AND "lead_time_days" NOT GLOB '?*-*');

-- S06 SupplierMaterial.lead_time_days
SELECT record_uid, "lead_time_days" FROM "SupplierMaterial" WHERE "lead_time_days" IS NOT NULL AND "lead_time_days" <> '' AND ("lead_time_days" NOT GLOB '*[^0-9-]*' AND "lead_time_days" GLOB '*[0-9]*' AND "lead_time_days" NOT GLOB '?*-*') AND (CAST("lead_time_days" AS REAL) < 0);

-- S07 SupplierMaterial.min_order_qty
SELECT record_uid, "min_order_qty" FROM "SupplierMaterial" WHERE "min_order_qty" = '';

-- S02 SupplierMaterial.min_order_qty
SELECT record_uid, "min_order_qty" FROM "SupplierMaterial" WHERE "min_order_qty" IS NOT NULL AND "min_order_qty" <> '' AND NOT ("min_order_qty" NOT GLOB '*[^0-9.-]*' AND "min_order_qty" GLOB '*[0-9]*' AND "min_order_qty" NOT GLOB '?*-*' AND (length("min_order_qty") - length(replace("min_order_qty", '.', ''))) <= 1);

-- S06 SupplierMaterial.min_order_qty
SELECT record_uid, "min_order_qty" FROM "SupplierMaterial" WHERE "min_order_qty" IS NOT NULL AND "min_order_qty" <> '' AND ("min_order_qty" NOT GLOB '*[^0-9.-]*' AND "min_order_qty" GLOB '*[0-9]*' AND "min_order_qty" NOT GLOB '?*-*' AND (length("min_order_qty") - length(replace("min_order_qty", '.', ''))) <= 1) AND (CAST("min_order_qty" AS REAL) < 0);

-- S01 SupplierMaterial.is_preferred
SELECT record_uid, "is_preferred" FROM "SupplierMaterial" WHERE "is_preferred" IS NULL OR "is_preferred" = '';

-- S02 SupplierMaterial.is_preferred
SELECT record_uid, "is_preferred" FROM "SupplierMaterial" WHERE "is_preferred" IS NOT NULL AND "is_preferred" NOT IN (0, 1);

-- S05 SupplierMaterial.record_uid
SELECT record_uid, record_uid FROM "SupplierMaterial" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 BOM.record_uid
SELECT record_uid, "record_uid" FROM "BOM" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 BOM.origin_class
SELECT record_uid, "origin_class" FROM "BOM" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 BOM.origin_class
SELECT record_uid, "origin_class" FROM "BOM" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 BOM.bom_id
SELECT record_uid, "bom_id" FROM "BOM" WHERE "bom_id" IS NULL OR "bom_id" = '';

-- S01 BOM.product_id
SELECT record_uid, "product_id" FROM "BOM" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 BOM.bom_version
SELECT record_uid, "bom_version" FROM "BOM" WHERE "bom_version" IS NULL OR "bom_version" = '';

-- S01 BOM.status
SELECT record_uid, "status" FROM "BOM" WHERE "status" IS NULL OR "status" = '';

-- S04 BOM.status
SELECT record_uid, "status" FROM "BOM" WHERE "status" IS NOT NULL AND "status" <> '' AND "status" NOT IN ('DRAFT', 'APPROVED');

-- S01 BOM.is_active
SELECT record_uid, "is_active" FROM "BOM" WHERE "is_active" IS NULL OR "is_active" = '';

-- S02 BOM.is_active
SELECT record_uid, "is_active" FROM "BOM" WHERE "is_active" IS NOT NULL AND "is_active" NOT IN (0, 1);

-- S01 BOM.valid_from
SELECT record_uid, "valid_from" FROM "BOM" WHERE "valid_from" IS NULL OR "valid_from" = '';

-- S03 BOM.valid_from
SELECT record_uid, "valid_from" FROM "BOM" WHERE "valid_from" IS NOT NULL AND "valid_from" <> '' AND NOT (date("valid_from") IS NOT NULL AND date("valid_from") = "valid_from");

-- S07 BOM.valid_to
SELECT record_uid, "valid_to" FROM "BOM" WHERE "valid_to" = '';

-- S03 BOM.valid_to
SELECT record_uid, "valid_to" FROM "BOM" WHERE "valid_to" IS NOT NULL AND "valid_to" <> '' AND NOT (date("valid_to") IS NOT NULL AND date("valid_to") = "valid_to");

-- S01 BOM.min_qty
SELECT record_uid, "min_qty" FROM "BOM" WHERE "min_qty" IS NULL OR "min_qty" = '';

-- S02 BOM.min_qty
SELECT record_uid, "min_qty" FROM "BOM" WHERE "min_qty" IS NOT NULL AND "min_qty" <> '' AND NOT ("min_qty" NOT GLOB '*[^0-9.-]*' AND "min_qty" GLOB '*[0-9]*' AND "min_qty" NOT GLOB '?*-*' AND (length("min_qty") - length(replace("min_qty", '.', ''))) <= 1);

-- S06 BOM.min_qty
SELECT record_uid, "min_qty" FROM "BOM" WHERE "min_qty" IS NOT NULL AND "min_qty" <> '' AND ("min_qty" NOT GLOB '*[^0-9.-]*' AND "min_qty" GLOB '*[0-9]*' AND "min_qty" NOT GLOB '?*-*' AND (length("min_qty") - length(replace("min_qty", '.', ''))) <= 1) AND (CAST("min_qty" AS REAL) < 0);

-- S07 BOM.max_qty
SELECT record_uid, "max_qty" FROM "BOM" WHERE "max_qty" = '';

-- S02 BOM.max_qty
SELECT record_uid, "max_qty" FROM "BOM" WHERE "max_qty" IS NOT NULL AND "max_qty" <> '' AND NOT ("max_qty" NOT GLOB '*[^0-9.-]*' AND "max_qty" GLOB '*[0-9]*' AND "max_qty" NOT GLOB '?*-*' AND (length("max_qty") - length(replace("max_qty", '.', ''))) <= 1);

-- S07 BOM.site_id
SELECT record_uid, "site_id" FROM "BOM" WHERE "site_id" = '';

-- S01 BOM.base_qty
SELECT record_uid, "base_qty" FROM "BOM" WHERE "base_qty" IS NULL OR "base_qty" = '';

-- S02 BOM.base_qty
SELECT record_uid, "base_qty" FROM "BOM" WHERE "base_qty" IS NOT NULL AND "base_qty" <> '' AND NOT ("base_qty" NOT GLOB '*[^0-9.-]*' AND "base_qty" GLOB '*[0-9]*' AND "base_qty" NOT GLOB '?*-*' AND (length("base_qty") - length(replace("base_qty", '.', ''))) <= 1);

-- S06 BOM.base_qty
SELECT record_uid, "base_qty" FROM "BOM" WHERE "base_qty" IS NOT NULL AND "base_qty" <> '' AND ("base_qty" NOT GLOB '*[^0-9.-]*' AND "base_qty" GLOB '*[0-9]*' AND "base_qty" NOT GLOB '?*-*' AND (length("base_qty") - length(replace("base_qty", '.', ''))) <= 1) AND (CAST("base_qty" AS REAL) <= 0);

-- S05 BOM.record_uid
SELECT record_uid, record_uid FROM "BOM" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 BOMLine.record_uid
SELECT record_uid, "record_uid" FROM "BOMLine" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 BOMLine.origin_class
SELECT record_uid, "origin_class" FROM "BOMLine" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 BOMLine.origin_class
SELECT record_uid, "origin_class" FROM "BOMLine" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 BOMLine.bom_id
SELECT record_uid, "bom_id" FROM "BOMLine" WHERE "bom_id" IS NULL OR "bom_id" = '';

-- S01 BOMLine.line_no
SELECT record_uid, "line_no" FROM "BOMLine" WHERE "line_no" IS NULL OR "line_no" = '';

-- S02 BOMLine.line_no
SELECT record_uid, "line_no" FROM "BOMLine" WHERE "line_no" IS NOT NULL AND "line_no" <> '' AND NOT ("line_no" NOT GLOB '*[^0-9-]*' AND "line_no" GLOB '*[0-9]*' AND "line_no" NOT GLOB '?*-*');

-- S06 BOMLine.line_no
SELECT record_uid, "line_no" FROM "BOMLine" WHERE "line_no" IS NOT NULL AND "line_no" <> '' AND ("line_no" NOT GLOB '*[^0-9-]*' AND "line_no" GLOB '*[0-9]*' AND "line_no" NOT GLOB '?*-*') AND (CAST("line_no" AS REAL) < 1);

-- S01 BOMLine.component_type
SELECT record_uid, "component_type" FROM "BOMLine" WHERE "component_type" IS NULL OR "component_type" = '';

-- S04 BOMLine.component_type
SELECT record_uid, "component_type" FROM "BOMLine" WHERE "component_type" IS NOT NULL AND "component_type" <> '' AND "component_type" NOT IN ('MATERIAL', 'PRODUCT');

-- S07 BOMLine.component_material_id
SELECT record_uid, "component_material_id" FROM "BOMLine" WHERE "component_material_id" = '';

-- S07 BOMLine.component_product_id
SELECT record_uid, "component_product_id" FROM "BOMLine" WHERE "component_product_id" = '';

-- S01 BOMLine.qty_per
SELECT record_uid, "qty_per" FROM "BOMLine" WHERE "qty_per" IS NULL OR "qty_per" = '';

-- S02 BOMLine.qty_per
SELECT record_uid, "qty_per" FROM "BOMLine" WHERE "qty_per" IS NOT NULL AND "qty_per" <> '' AND NOT ("qty_per" NOT GLOB '*[^0-9.-]*' AND "qty_per" GLOB '*[0-9]*' AND "qty_per" NOT GLOB '?*-*' AND (length("qty_per") - length(replace("qty_per", '.', ''))) <= 1);

-- S06 BOMLine.qty_per
SELECT record_uid, "qty_per" FROM "BOMLine" WHERE "qty_per" IS NOT NULL AND "qty_per" <> '' AND ("qty_per" NOT GLOB '*[^0-9.-]*' AND "qty_per" GLOB '*[0-9]*' AND "qty_per" NOT GLOB '?*-*' AND (length("qty_per") - length(replace("qty_per", '.', ''))) <= 1) AND (CAST("qty_per" AS REAL) <= 0);

-- S01 BOMLine.unit
SELECT record_uid, "unit" FROM "BOMLine" WHERE "unit" IS NULL OR "unit" = '';

-- S07 BOMLine.scrap_rate
SELECT record_uid, "scrap_rate" FROM "BOMLine" WHERE "scrap_rate" = '';

-- S02 BOMLine.scrap_rate
SELECT record_uid, "scrap_rate" FROM "BOMLine" WHERE "scrap_rate" IS NOT NULL AND "scrap_rate" <> '' AND NOT ("scrap_rate" NOT GLOB '*[^0-9.-]*' AND "scrap_rate" GLOB '*[0-9]*' AND "scrap_rate" NOT GLOB '?*-*' AND (length("scrap_rate") - length(replace("scrap_rate", '.', ''))) <= 1);

-- S06 BOMLine.scrap_rate
SELECT record_uid, "scrap_rate" FROM "BOMLine" WHERE "scrap_rate" IS NOT NULL AND "scrap_rate" <> '' AND ("scrap_rate" NOT GLOB '*[^0-9.-]*' AND "scrap_rate" GLOB '*[0-9]*' AND "scrap_rate" NOT GLOB '?*-*' AND (length("scrap_rate") - length(replace("scrap_rate", '.', ''))) <= 1) AND (CAST("scrap_rate" AS REAL) < 0 OR CAST("scrap_rate" AS REAL) >= 1);

-- S07 BOMLine.line_type
SELECT record_uid, "line_type" FROM "BOMLine" WHERE "line_type" = '';

-- S04 BOMLine.line_type
SELECT record_uid, "line_type" FROM "BOMLine" WHERE "line_type" IS NOT NULL AND "line_type" <> '' AND "line_type" NOT IN ('ITEM');

-- S05 BOMLine.record_uid
SELECT record_uid, record_uid FROM "BOMLine" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Order.record_uid
SELECT record_uid, "record_uid" FROM "Order" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Order.origin_class
SELECT record_uid, "origin_class" FROM "Order" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Order.origin_class
SELECT record_uid, "origin_class" FROM "Order" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Order.order_id
SELECT record_uid, "order_id" FROM "Order" WHERE "order_id" IS NULL OR "order_id" = '';

-- S01 Order.product_id
SELECT record_uid, "product_id" FROM "Order" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 Order.order_qty
SELECT record_uid, "order_qty" FROM "Order" WHERE "order_qty" IS NULL OR "order_qty" = '';

-- S02 Order.order_qty
SELECT record_uid, "order_qty" FROM "Order" WHERE "order_qty" IS NOT NULL AND "order_qty" <> '' AND NOT ("order_qty" NOT GLOB '*[^0-9.-]*' AND "order_qty" GLOB '*[0-9]*' AND "order_qty" NOT GLOB '?*-*' AND (length("order_qty") - length(replace("order_qty", '.', ''))) <= 1);

-- S06 Order.order_qty
SELECT record_uid, "order_qty" FROM "Order" WHERE "order_qty" IS NOT NULL AND "order_qty" <> '' AND ("order_qty" NOT GLOB '*[^0-9.-]*' AND "order_qty" GLOB '*[0-9]*' AND "order_qty" NOT GLOB '?*-*' AND (length("order_qty") - length(replace("order_qty", '.', ''))) <= 1) AND (CAST("order_qty" AS REAL) <= 0);

-- S01 Order.unit
SELECT record_uid, "unit" FROM "Order" WHERE "unit" IS NULL OR "unit" = '';

-- S01 Order.order_date
SELECT record_uid, "order_date" FROM "Order" WHERE "order_date" IS NULL OR "order_date" = '';

-- S03 Order.order_date
SELECT record_uid, "order_date" FROM "Order" WHERE "order_date" IS NOT NULL AND "order_date" <> '' AND NOT (date("order_date") IS NOT NULL AND date("order_date") = "order_date");

-- S01 Order.due_date
SELECT record_uid, "due_date" FROM "Order" WHERE "due_date" IS NULL OR "due_date" = '';

-- S03 Order.due_date
SELECT record_uid, "due_date" FROM "Order" WHERE "due_date" IS NOT NULL AND "due_date" <> '' AND NOT (date("due_date") IS NOT NULL AND date("due_date") = "due_date");

-- S01 Order.priority
SELECT record_uid, "priority" FROM "Order" WHERE "priority" IS NULL OR "priority" = '';

-- S04 Order.priority
SELECT record_uid, "priority" FROM "Order" WHERE "priority" IS NOT NULL AND "priority" <> '' AND "priority" NOT IN ('NORMAL', 'URGENT');

-- S01 Order.status
SELECT record_uid, "status" FROM "Order" WHERE "status" IS NULL OR "status" = '';

-- S04 Order.status
SELECT record_uid, "status" FROM "Order" WHERE "status" IS NOT NULL AND "status" <> '' AND "status" NOT IN ('OPEN', 'CLOSED', 'CANCELLED');

-- S05 Order.record_uid
SELECT record_uid, record_uid FROM "Order" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 SalesHistory.record_uid
SELECT record_uid, "record_uid" FROM "SalesHistory" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 SalesHistory.origin_class
SELECT record_uid, "origin_class" FROM "SalesHistory" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 SalesHistory.origin_class
SELECT record_uid, "origin_class" FROM "SalesHistory" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 SalesHistory.product_id
SELECT record_uid, "product_id" FROM "SalesHistory" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 SalesHistory.period_start
SELECT record_uid, "period_start" FROM "SalesHistory" WHERE "period_start" IS NULL OR "period_start" = '';

-- S03 SalesHistory.period_start
SELECT record_uid, "period_start" FROM "SalesHistory" WHERE "period_start" IS NOT NULL AND "period_start" <> '' AND NOT (date("period_start") IS NOT NULL AND date("period_start") = "period_start");

-- S01 SalesHistory.period_grain
SELECT record_uid, "period_grain" FROM "SalesHistory" WHERE "period_grain" IS NULL OR "period_grain" = '';

-- S04 SalesHistory.period_grain
SELECT record_uid, "period_grain" FROM "SalesHistory" WHERE "period_grain" IS NOT NULL AND "period_grain" <> '' AND "period_grain" NOT IN ('DAY', 'WEEK');

-- S01 SalesHistory.sales_qty
SELECT record_uid, "sales_qty" FROM "SalesHistory" WHERE "sales_qty" IS NULL OR "sales_qty" = '';

-- S02 SalesHistory.sales_qty
SELECT record_uid, "sales_qty" FROM "SalesHistory" WHERE "sales_qty" IS NOT NULL AND "sales_qty" <> '' AND NOT ("sales_qty" NOT GLOB '*[^0-9.-]*' AND "sales_qty" GLOB '*[0-9]*' AND "sales_qty" NOT GLOB '?*-*' AND (length("sales_qty") - length(replace("sales_qty", '.', ''))) <= 1);

-- S06 SalesHistory.sales_qty
SELECT record_uid, "sales_qty" FROM "SalesHistory" WHERE "sales_qty" IS NOT NULL AND "sales_qty" <> '' AND ("sales_qty" NOT GLOB '*[^0-9.-]*' AND "sales_qty" GLOB '*[0-9]*' AND "sales_qty" NOT GLOB '?*-*' AND (length("sales_qty") - length(replace("sales_qty", '.', ''))) <= 1) AND (CAST("sales_qty" AS REAL) < 0);

-- S07 SalesHistory.source_series_id
SELECT record_uid, "source_series_id" FROM "SalesHistory" WHERE "source_series_id" = '';

-- S01 SalesHistory.generation_method
SELECT record_uid, "generation_method" FROM "SalesHistory" WHERE "generation_method" IS NULL OR "generation_method" = '';

-- S04 SalesHistory.generation_method
SELECT record_uid, "generation_method" FROM "SalesHistory" WHERE "generation_method" IS NOT NULL AND "generation_method" <> '' AND "generation_method" NOT IN ('GENERATED', 'ALLOCATED', 'MAPPED', 'TRANSFORMED');

-- S07 SalesHistory.derived_from_record_uid
SELECT record_uid, "derived_from_record_uid" FROM "SalesHistory" WHERE "derived_from_record_uid" = '';

-- S07 SalesHistory.allocation_share
SELECT record_uid, "allocation_share" FROM "SalesHistory" WHERE "allocation_share" = '';

-- S02 SalesHistory.allocation_share
SELECT record_uid, "allocation_share" FROM "SalesHistory" WHERE "allocation_share" IS NOT NULL AND "allocation_share" <> '' AND NOT ("allocation_share" NOT GLOB '*[^0-9.-]*' AND "allocation_share" GLOB '*[0-9]*' AND "allocation_share" NOT GLOB '?*-*' AND (length("allocation_share") - length(replace("allocation_share", '.', ''))) <= 1);

-- S06 SalesHistory.allocation_share
SELECT record_uid, "allocation_share" FROM "SalesHistory" WHERE "allocation_share" IS NOT NULL AND "allocation_share" <> '' AND ("allocation_share" NOT GLOB '*[^0-9.-]*' AND "allocation_share" GLOB '*[0-9]*' AND "allocation_share" NOT GLOB '?*-*' AND (length("allocation_share") - length(replace("allocation_share", '.', ''))) <= 1) AND (CAST("allocation_share" AS REAL) <= 0 OR CAST("allocation_share" AS REAL) > 1);

-- S07 SalesHistory.date_is_synthetic
SELECT record_uid, "date_is_synthetic" FROM "SalesHistory" WHERE "date_is_synthetic" = '';

-- S02 SalesHistory.date_is_synthetic
SELECT record_uid, "date_is_synthetic" FROM "SalesHistory" WHERE "date_is_synthetic" IS NOT NULL AND "date_is_synthetic" NOT IN (0, 1);

-- S07 SalesHistory.source_day_of_week_code
SELECT record_uid, "source_day_of_week_code" FROM "SalesHistory" WHERE "source_day_of_week_code" = '';

-- S02 SalesHistory.source_day_of_week_code
SELECT record_uid, "source_day_of_week_code" FROM "SalesHistory" WHERE "source_day_of_week_code" IS NOT NULL AND "source_day_of_week_code" <> '' AND NOT ("source_day_of_week_code" NOT GLOB '*[^0-9-]*' AND "source_day_of_week_code" GLOB '*[0-9]*' AND "source_day_of_week_code" NOT GLOB '?*-*');

-- S05 SalesHistory.record_uid
SELECT record_uid, record_uid FROM "SalesHistory" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Inventory.record_uid
SELECT record_uid, "record_uid" FROM "Inventory" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Inventory.origin_class
SELECT record_uid, "origin_class" FROM "Inventory" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Inventory.origin_class
SELECT record_uid, "origin_class" FROM "Inventory" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Inventory.item_type
SELECT record_uid, "item_type" FROM "Inventory" WHERE "item_type" IS NULL OR "item_type" = '';

-- S04 Inventory.item_type
SELECT record_uid, "item_type" FROM "Inventory" WHERE "item_type" IS NOT NULL AND "item_type" <> '' AND "item_type" NOT IN ('PRODUCT', 'MATERIAL');

-- S01 Inventory.item_id
SELECT record_uid, "item_id" FROM "Inventory" WHERE "item_id" IS NULL OR "item_id" = '';

-- S01 Inventory.as_of_date
SELECT record_uid, "as_of_date" FROM "Inventory" WHERE "as_of_date" IS NULL OR "as_of_date" = '';

-- S03 Inventory.as_of_date
SELECT record_uid, "as_of_date" FROM "Inventory" WHERE "as_of_date" IS NOT NULL AND "as_of_date" <> '' AND NOT (date("as_of_date") IS NOT NULL AND date("as_of_date") = "as_of_date");

-- S01 Inventory.on_hand_qty
SELECT record_uid, "on_hand_qty" FROM "Inventory" WHERE "on_hand_qty" IS NULL OR "on_hand_qty" = '';

-- S02 Inventory.on_hand_qty
SELECT record_uid, "on_hand_qty" FROM "Inventory" WHERE "on_hand_qty" IS NOT NULL AND "on_hand_qty" <> '' AND NOT ("on_hand_qty" NOT GLOB '*[^0-9.-]*' AND "on_hand_qty" GLOB '*[0-9]*' AND "on_hand_qty" NOT GLOB '?*-*' AND (length("on_hand_qty") - length(replace("on_hand_qty", '.', ''))) <= 1);

-- V01 Inventory.on_hand_qty
SELECT record_uid, "on_hand_qty" FROM "Inventory" WHERE "on_hand_qty" IS NOT NULL AND "on_hand_qty" <> '' AND ("on_hand_qty" NOT GLOB '*[^0-9.-]*' AND "on_hand_qty" GLOB '*[0-9]*' AND "on_hand_qty" NOT GLOB '?*-*' AND (length("on_hand_qty") - length(replace("on_hand_qty", '.', ''))) <= 1) AND (CAST("on_hand_qty" AS REAL) < 0);

-- S07 Inventory.allocated_qty
SELECT record_uid, "allocated_qty" FROM "Inventory" WHERE "allocated_qty" = '';

-- S02 Inventory.allocated_qty
SELECT record_uid, "allocated_qty" FROM "Inventory" WHERE "allocated_qty" IS NOT NULL AND "allocated_qty" <> '' AND NOT ("allocated_qty" NOT GLOB '*[^0-9.-]*' AND "allocated_qty" GLOB '*[0-9]*' AND "allocated_qty" NOT GLOB '?*-*' AND (length("allocated_qty") - length(replace("allocated_qty", '.', ''))) <= 1);

-- S06 Inventory.allocated_qty
SELECT record_uid, "allocated_qty" FROM "Inventory" WHERE "allocated_qty" IS NOT NULL AND "allocated_qty" <> '' AND ("allocated_qty" NOT GLOB '*[^0-9.-]*' AND "allocated_qty" GLOB '*[0-9]*' AND "allocated_qty" NOT GLOB '?*-*' AND (length("allocated_qty") - length(replace("allocated_qty", '.', ''))) <= 1) AND (CAST("allocated_qty" AS REAL) < 0);

-- S07 Inventory.on_order_qty
SELECT record_uid, "on_order_qty" FROM "Inventory" WHERE "on_order_qty" = '';

-- S02 Inventory.on_order_qty
SELECT record_uid, "on_order_qty" FROM "Inventory" WHERE "on_order_qty" IS NOT NULL AND "on_order_qty" <> '' AND NOT ("on_order_qty" NOT GLOB '*[^0-9.-]*' AND "on_order_qty" GLOB '*[0-9]*' AND "on_order_qty" NOT GLOB '?*-*' AND (length("on_order_qty") - length(replace("on_order_qty", '.', ''))) <= 1);

-- S06 Inventory.on_order_qty
SELECT record_uid, "on_order_qty" FROM "Inventory" WHERE "on_order_qty" IS NOT NULL AND "on_order_qty" <> '' AND ("on_order_qty" NOT GLOB '*[^0-9.-]*' AND "on_order_qty" GLOB '*[0-9]*' AND "on_order_qty" NOT GLOB '?*-*' AND (length("on_order_qty") - length(replace("on_order_qty", '.', ''))) <= 1) AND (CAST("on_order_qty" AS REAL) < 0);

-- S07 Inventory.expected_receipt_date
SELECT record_uid, "expected_receipt_date" FROM "Inventory" WHERE "expected_receipt_date" = '';

-- S03 Inventory.expected_receipt_date
SELECT record_uid, "expected_receipt_date" FROM "Inventory" WHERE "expected_receipt_date" IS NOT NULL AND "expected_receipt_date" <> '' AND NOT (date("expected_receipt_date") IS NOT NULL AND date("expected_receipt_date") = "expected_receipt_date");

-- S01 Inventory.unit
SELECT record_uid, "unit" FROM "Inventory" WHERE "unit" IS NULL OR "unit" = '';

-- S05 Inventory.record_uid
SELECT record_uid, record_uid FROM "Inventory" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Resource.record_uid
SELECT record_uid, "record_uid" FROM "Resource" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Resource.origin_class
SELECT record_uid, "origin_class" FROM "Resource" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Resource.origin_class
SELECT record_uid, "origin_class" FROM "Resource" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Resource.resource_id
SELECT record_uid, "resource_id" FROM "Resource" WHERE "resource_id" IS NULL OR "resource_id" = '';

-- S01 Resource.resource_name
SELECT record_uid, "resource_name" FROM "Resource" WHERE "resource_name" IS NULL OR "resource_name" = '';

-- S01 Resource.resource_type
SELECT record_uid, "resource_type" FROM "Resource" WHERE "resource_type" IS NULL OR "resource_type" = '';

-- S04 Resource.resource_type
SELECT record_uid, "resource_type" FROM "Resource" WHERE "resource_type" IS NOT NULL AND "resource_type" <> '' AND "resource_type" NOT IN ('MACHINE', 'LINE', 'WORKCENTER');

-- S01 Resource.regular_hours_per_day
SELECT record_uid, "regular_hours_per_day" FROM "Resource" WHERE "regular_hours_per_day" IS NULL OR "regular_hours_per_day" = '';

-- S02 Resource.regular_hours_per_day
SELECT record_uid, "regular_hours_per_day" FROM "Resource" WHERE "regular_hours_per_day" IS NOT NULL AND "regular_hours_per_day" <> '' AND NOT ("regular_hours_per_day" NOT GLOB '*[^0-9.-]*' AND "regular_hours_per_day" GLOB '*[0-9]*' AND "regular_hours_per_day" NOT GLOB '?*-*' AND (length("regular_hours_per_day") - length(replace("regular_hours_per_day", '.', ''))) <= 1);

-- S06 Resource.regular_hours_per_day
SELECT record_uid, "regular_hours_per_day" FROM "Resource" WHERE "regular_hours_per_day" IS NOT NULL AND "regular_hours_per_day" <> '' AND ("regular_hours_per_day" NOT GLOB '*[^0-9.-]*' AND "regular_hours_per_day" GLOB '*[0-9]*' AND "regular_hours_per_day" NOT GLOB '?*-*' AND (length("regular_hours_per_day") - length(replace("regular_hours_per_day", '.', ''))) <= 1) AND (CAST("regular_hours_per_day" AS REAL) <= 0);

-- S01 Resource.overtime_hours_per_day_max
SELECT record_uid, "overtime_hours_per_day_max" FROM "Resource" WHERE "overtime_hours_per_day_max" IS NULL OR "overtime_hours_per_day_max" = '';

-- S02 Resource.overtime_hours_per_day_max
SELECT record_uid, "overtime_hours_per_day_max" FROM "Resource" WHERE "overtime_hours_per_day_max" IS NOT NULL AND "overtime_hours_per_day_max" <> '' AND NOT ("overtime_hours_per_day_max" NOT GLOB '*[^0-9.-]*' AND "overtime_hours_per_day_max" GLOB '*[0-9]*' AND "overtime_hours_per_day_max" NOT GLOB '?*-*' AND (length("overtime_hours_per_day_max") - length(replace("overtime_hours_per_day_max", '.', ''))) <= 1);

-- S06 Resource.overtime_hours_per_day_max
SELECT record_uid, "overtime_hours_per_day_max" FROM "Resource" WHERE "overtime_hours_per_day_max" IS NOT NULL AND "overtime_hours_per_day_max" <> '' AND ("overtime_hours_per_day_max" NOT GLOB '*[^0-9.-]*' AND "overtime_hours_per_day_max" GLOB '*[0-9]*' AND "overtime_hours_per_day_max" NOT GLOB '?*-*' AND (length("overtime_hours_per_day_max") - length(replace("overtime_hours_per_day_max", '.', ''))) <= 1) AND (CAST("overtime_hours_per_day_max" AS REAL) < 0);

-- S01 Resource.cost_per_hour
SELECT record_uid, "cost_per_hour" FROM "Resource" WHERE "cost_per_hour" IS NULL OR "cost_per_hour" = '';

-- S02 Resource.cost_per_hour
SELECT record_uid, "cost_per_hour" FROM "Resource" WHERE "cost_per_hour" IS NOT NULL AND "cost_per_hour" <> '' AND NOT ("cost_per_hour" NOT GLOB '*[^0-9.-]*' AND "cost_per_hour" GLOB '*[0-9]*' AND "cost_per_hour" NOT GLOB '?*-*' AND (length("cost_per_hour") - length(replace("cost_per_hour", '.', ''))) <= 1);

-- S06 Resource.cost_per_hour
SELECT record_uid, "cost_per_hour" FROM "Resource" WHERE "cost_per_hour" IS NOT NULL AND "cost_per_hour" <> '' AND ("cost_per_hour" NOT GLOB '*[^0-9.-]*' AND "cost_per_hour" GLOB '*[0-9]*' AND "cost_per_hour" NOT GLOB '?*-*' AND (length("cost_per_hour") - length(replace("cost_per_hour", '.', ''))) <= 1) AND (CAST("cost_per_hour" AS REAL) < 0);

-- S01 Resource.overtime_cost_per_hour
SELECT record_uid, "overtime_cost_per_hour" FROM "Resource" WHERE "overtime_cost_per_hour" IS NULL OR "overtime_cost_per_hour" = '';

-- S02 Resource.overtime_cost_per_hour
SELECT record_uid, "overtime_cost_per_hour" FROM "Resource" WHERE "overtime_cost_per_hour" IS NOT NULL AND "overtime_cost_per_hour" <> '' AND NOT ("overtime_cost_per_hour" NOT GLOB '*[^0-9.-]*' AND "overtime_cost_per_hour" GLOB '*[0-9]*' AND "overtime_cost_per_hour" NOT GLOB '?*-*' AND (length("overtime_cost_per_hour") - length(replace("overtime_cost_per_hour", '.', ''))) <= 1);

-- S06 Resource.overtime_cost_per_hour
SELECT record_uid, "overtime_cost_per_hour" FROM "Resource" WHERE "overtime_cost_per_hour" IS NOT NULL AND "overtime_cost_per_hour" <> '' AND ("overtime_cost_per_hour" NOT GLOB '*[^0-9.-]*' AND "overtime_cost_per_hour" GLOB '*[0-9]*' AND "overtime_cost_per_hour" NOT GLOB '?*-*' AND (length("overtime_cost_per_hour") - length(replace("overtime_cost_per_hour", '.', ''))) <= 1) AND (CAST("overtime_cost_per_hour" AS REAL) < 0);

-- S05 Resource.record_uid
SELECT record_uid, record_uid FROM "Resource" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 Operation.record_uid
SELECT record_uid, "record_uid" FROM "Operation" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 Operation.origin_class
SELECT record_uid, "origin_class" FROM "Operation" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 Operation.origin_class
SELECT record_uid, "origin_class" FROM "Operation" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 Operation.operation_id
SELECT record_uid, "operation_id" FROM "Operation" WHERE "operation_id" IS NULL OR "operation_id" = '';

-- S01 Operation.product_id
SELECT record_uid, "product_id" FROM "Operation" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 Operation.sequence_no
SELECT record_uid, "sequence_no" FROM "Operation" WHERE "sequence_no" IS NULL OR "sequence_no" = '';

-- S02 Operation.sequence_no
SELECT record_uid, "sequence_no" FROM "Operation" WHERE "sequence_no" IS NOT NULL AND "sequence_no" <> '' AND NOT ("sequence_no" NOT GLOB '*[^0-9-]*' AND "sequence_no" GLOB '*[0-9]*' AND "sequence_no" NOT GLOB '?*-*');

-- S06 Operation.sequence_no
SELECT record_uid, "sequence_no" FROM "Operation" WHERE "sequence_no" IS NOT NULL AND "sequence_no" <> '' AND ("sequence_no" NOT GLOB '*[^0-9-]*' AND "sequence_no" GLOB '*[0-9]*' AND "sequence_no" NOT GLOB '?*-*') AND (CAST("sequence_no" AS REAL) < 1);

-- S01 Operation.resource_id
SELECT record_uid, "resource_id" FROM "Operation" WHERE "resource_id" IS NULL OR "resource_id" = '';

-- S01 Operation.run_time_per_unit_h
SELECT record_uid, "run_time_per_unit_h" FROM "Operation" WHERE "run_time_per_unit_h" IS NULL OR "run_time_per_unit_h" = '';

-- S02 Operation.run_time_per_unit_h
SELECT record_uid, "run_time_per_unit_h" FROM "Operation" WHERE "run_time_per_unit_h" IS NOT NULL AND "run_time_per_unit_h" <> '' AND NOT ("run_time_per_unit_h" NOT GLOB '*[^0-9.-]*' AND "run_time_per_unit_h" GLOB '*[0-9]*' AND "run_time_per_unit_h" NOT GLOB '?*-*' AND (length("run_time_per_unit_h") - length(replace("run_time_per_unit_h", '.', ''))) <= 1);

-- S06 Operation.run_time_per_unit_h
SELECT record_uid, "run_time_per_unit_h" FROM "Operation" WHERE "run_time_per_unit_h" IS NOT NULL AND "run_time_per_unit_h" <> '' AND ("run_time_per_unit_h" NOT GLOB '*[^0-9.-]*' AND "run_time_per_unit_h" GLOB '*[0-9]*' AND "run_time_per_unit_h" NOT GLOB '?*-*' AND (length("run_time_per_unit_h") - length(replace("run_time_per_unit_h", '.', ''))) <= 1) AND (CAST("run_time_per_unit_h" AS REAL) <= 0);

-- S01 Operation.setup_time_h
SELECT record_uid, "setup_time_h" FROM "Operation" WHERE "setup_time_h" IS NULL OR "setup_time_h" = '';

-- S02 Operation.setup_time_h
SELECT record_uid, "setup_time_h" FROM "Operation" WHERE "setup_time_h" IS NOT NULL AND "setup_time_h" <> '' AND NOT ("setup_time_h" NOT GLOB '*[^0-9.-]*' AND "setup_time_h" GLOB '*[0-9]*' AND "setup_time_h" NOT GLOB '?*-*' AND (length("setup_time_h") - length(replace("setup_time_h", '.', ''))) <= 1);

-- S06 Operation.setup_time_h
SELECT record_uid, "setup_time_h" FROM "Operation" WHERE "setup_time_h" IS NOT NULL AND "setup_time_h" <> '' AND ("setup_time_h" NOT GLOB '*[^0-9.-]*' AND "setup_time_h" GLOB '*[0-9]*' AND "setup_time_h" NOT GLOB '?*-*' AND (length("setup_time_h") - length(replace("setup_time_h", '.', ''))) <= 1) AND (CAST("setup_time_h" AS REAL) < 0);

-- S05 Operation.record_uid
SELECT record_uid, record_uid FROM "Operation" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 ProductionPlan.record_uid
SELECT record_uid, "record_uid" FROM "ProductionPlan" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 ProductionPlan.origin_class
SELECT record_uid, "origin_class" FROM "ProductionPlan" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 ProductionPlan.origin_class
SELECT record_uid, "origin_class" FROM "ProductionPlan" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 ProductionPlan.plan_id
SELECT record_uid, "plan_id" FROM "ProductionPlan" WHERE "plan_id" IS NULL OR "plan_id" = '';

-- S01 ProductionPlan.plan_name
SELECT record_uid, "plan_name" FROM "ProductionPlan" WHERE "plan_name" IS NULL OR "plan_name" = '';

-- S01 ProductionPlan.horizon_start
SELECT record_uid, "horizon_start" FROM "ProductionPlan" WHERE "horizon_start" IS NULL OR "horizon_start" = '';

-- S03 ProductionPlan.horizon_start
SELECT record_uid, "horizon_start" FROM "ProductionPlan" WHERE "horizon_start" IS NOT NULL AND "horizon_start" <> '' AND NOT (date("horizon_start") IS NOT NULL AND date("horizon_start") = "horizon_start");

-- S01 ProductionPlan.horizon_end
SELECT record_uid, "horizon_end" FROM "ProductionPlan" WHERE "horizon_end" IS NULL OR "horizon_end" = '';

-- S03 ProductionPlan.horizon_end
SELECT record_uid, "horizon_end" FROM "ProductionPlan" WHERE "horizon_end" IS NOT NULL AND "horizon_end" <> '' AND NOT (date("horizon_end") IS NOT NULL AND date("horizon_end") = "horizon_end");

-- S01 ProductionPlan.generated_by
SELECT record_uid, "generated_by" FROM "ProductionPlan" WHERE "generated_by" IS NULL OR "generated_by" = '';

-- S04 ProductionPlan.generated_by
SELECT record_uid, "generated_by" FROM "ProductionPlan" WHERE "generated_by" IS NOT NULL AND "generated_by" <> '' AND "generated_by" NOT IN ('RULE', 'OPTIMIZER', 'MANUAL');

-- S01 ProductionPlan.overtime_allowed
SELECT record_uid, "overtime_allowed" FROM "ProductionPlan" WHERE "overtime_allowed" IS NULL OR "overtime_allowed" = '';

-- S02 ProductionPlan.overtime_allowed
SELECT record_uid, "overtime_allowed" FROM "ProductionPlan" WHERE "overtime_allowed" IS NOT NULL AND "overtime_allowed" NOT IN (0, 1);

-- S05 ProductionPlan.record_uid
SELECT record_uid, record_uid FROM "ProductionPlan" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S01 ProductionPlanLine.record_uid
SELECT record_uid, "record_uid" FROM "ProductionPlanLine" WHERE "record_uid" IS NULL OR "record_uid" = '';

-- S01 ProductionPlanLine.origin_class
SELECT record_uid, "origin_class" FROM "ProductionPlanLine" WHERE "origin_class" IS NULL OR "origin_class" = '';

-- S04 ProductionPlanLine.origin_class
SELECT record_uid, "origin_class" FROM "ProductionPlanLine" WHERE "origin_class" IS NOT NULL AND "origin_class" <> '' AND "origin_class" NOT IN ('SYNTHETIC', 'PUBLIC_DERIVED');

-- S01 ProductionPlanLine.plan_id
SELECT record_uid, "plan_id" FROM "ProductionPlanLine" WHERE "plan_id" IS NULL OR "plan_id" = '';

-- S01 ProductionPlanLine.line_no
SELECT record_uid, "line_no" FROM "ProductionPlanLine" WHERE "line_no" IS NULL OR "line_no" = '';

-- S02 ProductionPlanLine.line_no
SELECT record_uid, "line_no" FROM "ProductionPlanLine" WHERE "line_no" IS NOT NULL AND "line_no" <> '' AND NOT ("line_no" NOT GLOB '*[^0-9-]*' AND "line_no" GLOB '*[0-9]*' AND "line_no" NOT GLOB '?*-*');

-- S06 ProductionPlanLine.line_no
SELECT record_uid, "line_no" FROM "ProductionPlanLine" WHERE "line_no" IS NOT NULL AND "line_no" <> '' AND ("line_no" NOT GLOB '*[^0-9-]*' AND "line_no" GLOB '*[0-9]*' AND "line_no" NOT GLOB '?*-*') AND (CAST("line_no" AS REAL) < 1);

-- S01 ProductionPlanLine.product_id
SELECT record_uid, "product_id" FROM "ProductionPlanLine" WHERE "product_id" IS NULL OR "product_id" = '';

-- S01 ProductionPlanLine.period_start
SELECT record_uid, "period_start" FROM "ProductionPlanLine" WHERE "period_start" IS NULL OR "period_start" = '';

-- S03 ProductionPlanLine.period_start
SELECT record_uid, "period_start" FROM "ProductionPlanLine" WHERE "period_start" IS NOT NULL AND "period_start" <> '' AND NOT (date("period_start") IS NOT NULL AND date("period_start") = "period_start");

-- S01 ProductionPlanLine.planned_qty
SELECT record_uid, "planned_qty" FROM "ProductionPlanLine" WHERE "planned_qty" IS NULL OR "planned_qty" = '';

-- S02 ProductionPlanLine.planned_qty
SELECT record_uid, "planned_qty" FROM "ProductionPlanLine" WHERE "planned_qty" IS NOT NULL AND "planned_qty" <> '' AND NOT ("planned_qty" NOT GLOB '*[^0-9.-]*' AND "planned_qty" GLOB '*[0-9]*' AND "planned_qty" NOT GLOB '?*-*' AND (length("planned_qty") - length(replace("planned_qty", '.', ''))) <= 1);

-- S06 ProductionPlanLine.planned_qty
SELECT record_uid, "planned_qty" FROM "ProductionPlanLine" WHERE "planned_qty" IS NOT NULL AND "planned_qty" <> '' AND ("planned_qty" NOT GLOB '*[^0-9.-]*' AND "planned_qty" GLOB '*[0-9]*' AND "planned_qty" NOT GLOB '?*-*' AND (length("planned_qty") - length(replace("planned_qty", '.', ''))) <= 1) AND (CAST("planned_qty" AS REAL) < 0);

-- S01 ProductionPlanLine.unit
SELECT record_uid, "unit" FROM "ProductionPlanLine" WHERE "unit" IS NULL OR "unit" = '';

-- S01 ProductionPlanLine.production_mode
SELECT record_uid, "production_mode" FROM "ProductionPlanLine" WHERE "production_mode" IS NULL OR "production_mode" = '';

-- S04 ProductionPlanLine.production_mode
SELECT record_uid, "production_mode" FROM "ProductionPlanLine" WHERE "production_mode" IS NOT NULL AND "production_mode" <> '' AND "production_mode" NOT IN ('INHOUSE', 'OUTSOURCE');

-- S07 ProductionPlanLine.resource_id
SELECT record_uid, "resource_id" FROM "ProductionPlanLine" WHERE "resource_id" = '';

-- S05 ProductionPlanLine.record_uid
SELECT record_uid, record_uid FROM "ProductionPlanLine" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';

-- S08 Unit.*
SELECT t.record_uid, t."unit_code" FROM "Unit" t JOIN (SELECT "unit_code" FROM "Unit" WHERE "unit_code" IS NOT NULL AND "unit_code" <> '' GROUP BY "unit_code" HAVING COUNT(*) > 1) d USING ("unit_code");

-- S08 Product.*
SELECT t.record_uid, t."product_id" FROM "Product" t JOIN (SELECT "product_id" FROM "Product" WHERE "product_id" IS NOT NULL AND "product_id" <> '' GROUP BY "product_id" HAVING COUNT(*) > 1) d USING ("product_id");

-- S08 Material.*
SELECT t.record_uid, t."material_id" FROM "Material" t JOIN (SELECT "material_id" FROM "Material" WHERE "material_id" IS NOT NULL AND "material_id" <> '' GROUP BY "material_id" HAVING COUNT(*) > 1) d USING ("material_id");

-- S08 Supplier.*
SELECT t.record_uid, t."supplier_id" FROM "Supplier" t JOIN (SELECT "supplier_id" FROM "Supplier" WHERE "supplier_id" IS NOT NULL AND "supplier_id" <> '' GROUP BY "supplier_id" HAVING COUNT(*) > 1) d USING ("supplier_id");

-- S08 SupplierMaterial.*
SELECT t.record_uid, t."supplier_id" || '|' || t."material_id" FROM "SupplierMaterial" t JOIN (SELECT "supplier_id", "material_id" FROM "SupplierMaterial" WHERE "supplier_id" IS NOT NULL AND "supplier_id" <> '' AND "material_id" IS NOT NULL AND "material_id" <> '' GROUP BY "supplier_id", "material_id" HAVING COUNT(*) > 1) d USING ("supplier_id", "material_id");

-- S08 BOM.*
SELECT t.record_uid, t."bom_id" FROM "BOM" t JOIN (SELECT "bom_id" FROM "BOM" WHERE "bom_id" IS NOT NULL AND "bom_id" <> '' GROUP BY "bom_id" HAVING COUNT(*) > 1) d USING ("bom_id");

-- S08 BOMLine.*
SELECT t.record_uid, t."bom_id" || '|' || t."line_no" FROM "BOMLine" t JOIN (SELECT "bom_id", "line_no" FROM "BOMLine" WHERE "bom_id" IS NOT NULL AND "bom_id" <> '' AND "line_no" IS NOT NULL AND "line_no" <> '' GROUP BY "bom_id", "line_no" HAVING COUNT(*) > 1) d USING ("bom_id", "line_no");

-- S08 Order.*
SELECT t.record_uid, t."order_id" FROM "Order" t JOIN (SELECT "order_id" FROM "Order" WHERE "order_id" IS NOT NULL AND "order_id" <> '' GROUP BY "order_id" HAVING COUNT(*) > 1) d USING ("order_id");

-- S08 SalesHistory.*
SELECT t.record_uid, t."product_id" || '|' || t."period_start" || '|' || t."period_grain" FROM "SalesHistory" t JOIN (SELECT "product_id", "period_start", "period_grain" FROM "SalesHistory" WHERE "product_id" IS NOT NULL AND "product_id" <> '' AND "period_start" IS NOT NULL AND "period_start" <> '' AND "period_grain" IS NOT NULL AND "period_grain" <> '' GROUP BY "product_id", "period_start", "period_grain" HAVING COUNT(*) > 1) d USING ("product_id", "period_start", "period_grain");

-- S08 Resource.*
SELECT t.record_uid, t."resource_id" FROM "Resource" t JOIN (SELECT "resource_id" FROM "Resource" WHERE "resource_id" IS NOT NULL AND "resource_id" <> '' GROUP BY "resource_id" HAVING COUNT(*) > 1) d USING ("resource_id");

-- S08 Operation.*
SELECT t.record_uid, t."operation_id" FROM "Operation" t JOIN (SELECT "operation_id" FROM "Operation" WHERE "operation_id" IS NOT NULL AND "operation_id" <> '' GROUP BY "operation_id" HAVING COUNT(*) > 1) d USING ("operation_id");

-- S08 Operation.*
SELECT t.record_uid, t."product_id" || '|' || t."sequence_no" FROM "Operation" t JOIN (SELECT "product_id", "sequence_no" FROM "Operation" WHERE "product_id" IS NOT NULL AND "product_id" <> '' AND "sequence_no" IS NOT NULL AND "sequence_no" <> '' GROUP BY "product_id", "sequence_no" HAVING COUNT(*) > 1) d USING ("product_id", "sequence_no");

-- S08 ProductionPlan.*
SELECT t.record_uid, t."plan_id" FROM "ProductionPlan" t JOIN (SELECT "plan_id" FROM "ProductionPlan" WHERE "plan_id" IS NOT NULL AND "plan_id" <> '' GROUP BY "plan_id" HAVING COUNT(*) > 1) d USING ("plan_id");

-- S08 ProductionPlanLine.*
SELECT t.record_uid, t."plan_id" || '|' || t."line_no" FROM "ProductionPlanLine" t JOIN (SELECT "plan_id", "line_no" FROM "ProductionPlanLine" WHERE "plan_id" IS NOT NULL AND "plan_id" <> '' AND "line_no" IS NOT NULL AND "line_no" <> '' GROUP BY "plan_id", "line_no" HAVING COUNT(*) > 1) d USING ("plan_id", "line_no");

-- R01 BOM.product_id
SELECT c.record_uid, c."product_id" FROM "BOM" c LEFT JOIN "Product" p ON p."product_id" = c."product_id" WHERE c."product_id" IS NOT NULL AND c."product_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R01 Order.product_id
SELECT c.record_uid, c."product_id" FROM "Order" c LEFT JOIN "Product" p ON p."product_id" = c."product_id" WHERE c."product_id" IS NOT NULL AND c."product_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R01 Operation.product_id
SELECT c.record_uid, c."product_id" FROM "Operation" c LEFT JOIN "Product" p ON p."product_id" = c."product_id" WHERE c."product_id" IS NOT NULL AND c."product_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R01 ProductionPlanLine.product_id
SELECT c.record_uid, c."product_id" FROM "ProductionPlanLine" c LEFT JOIN "Product" p ON p."product_id" = c."product_id" WHERE c."product_id" IS NOT NULL AND c."product_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R01 SalesHistory.product_id
SELECT c.record_uid, c."product_id" FROM "SalesHistory" c LEFT JOIN "Product" p ON p."product_id" = c."product_id" WHERE c."product_id" IS NOT NULL AND c."product_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R01 BOMLine.component_product_id
SELECT c.record_uid, c."component_product_id" FROM "BOMLine" c LEFT JOIN "Product" p ON p."product_id" = c."component_product_id" WHERE c."component_product_id" IS NOT NULL AND c."component_product_id" <> '' AND (c.component_type = 'PRODUCT') AND p.record_uid IS NULL;

-- R01 Inventory.item_id
SELECT c.record_uid, c."item_id" FROM "Inventory" c LEFT JOIN "Product" p ON p."product_id" = c."item_id" WHERE c."item_id" IS NOT NULL AND c."item_id" <> '' AND (c.item_type = 'PRODUCT') AND p.record_uid IS NULL;

-- R02 BOMLine.component_material_id
SELECT c.record_uid, c."component_material_id" FROM "BOMLine" c LEFT JOIN "Material" p ON p."material_id" = c."component_material_id" WHERE c."component_material_id" IS NOT NULL AND c."component_material_id" <> '' AND (c.component_type = 'MATERIAL') AND p.record_uid IS NULL;

-- R02 SupplierMaterial.material_id
SELECT c.record_uid, c."material_id" FROM "SupplierMaterial" c LEFT JOIN "Material" p ON p."material_id" = c."material_id" WHERE c."material_id" IS NOT NULL AND c."material_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R02 Inventory.item_id
SELECT c.record_uid, c."item_id" FROM "Inventory" c LEFT JOIN "Material" p ON p."material_id" = c."item_id" WHERE c."item_id" IS NOT NULL AND c."item_id" <> '' AND (c.item_type = 'MATERIAL') AND p.record_uid IS NULL;

-- R03 SupplierMaterial.supplier_id
SELECT c.record_uid, c."supplier_id" FROM "SupplierMaterial" c LEFT JOIN "Supplier" p ON p."supplier_id" = c."supplier_id" WHERE c."supplier_id" IS NOT NULL AND c."supplier_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R04 BOMLine.bom_id
SELECT c.record_uid, c."bom_id" FROM "BOMLine" c LEFT JOIN "BOM" p ON p."bom_id" = c."bom_id" WHERE c."bom_id" IS NOT NULL AND c."bom_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R05 Operation.resource_id
SELECT c.record_uid, c."resource_id" FROM "Operation" c LEFT JOIN "Resource" p ON p."resource_id" = c."resource_id" WHERE c."resource_id" IS NOT NULL AND c."resource_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R05 ProductionPlanLine.resource_id
SELECT c.record_uid, c."resource_id" FROM "ProductionPlanLine" c LEFT JOIN "Resource" p ON p."resource_id" = c."resource_id" WHERE c."resource_id" IS NOT NULL AND c."resource_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R06 ProductionPlanLine.plan_id
SELECT c.record_uid, c."plan_id" FROM "ProductionPlanLine" c LEFT JOIN "ProductionPlan" p ON p."plan_id" = c."plan_id" WHERE c."plan_id" IS NOT NULL AND c."plan_id" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 Unit.base_unit_code
SELECT c.record_uid, c."base_unit_code" FROM "Unit" c LEFT JOIN "Unit" p ON p."unit_code" = c."base_unit_code" WHERE c."base_unit_code" IS NOT NULL AND c."base_unit_code" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 Product.base_unit
SELECT c.record_uid, c."base_unit" FROM "Product" c LEFT JOIN "Unit" p ON p."unit_code" = c."base_unit" WHERE c."base_unit" IS NOT NULL AND c."base_unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 Material.base_unit
SELECT c.record_uid, c."base_unit" FROM "Material" c LEFT JOIN "Unit" p ON p."unit_code" = c."base_unit" WHERE c."base_unit" IS NOT NULL AND c."base_unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 BOMLine.unit
SELECT c.record_uid, c."unit" FROM "BOMLine" c LEFT JOIN "Unit" p ON p."unit_code" = c."unit" WHERE c."unit" IS NOT NULL AND c."unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 Order.unit
SELECT c.record_uid, c."unit" FROM "Order" c LEFT JOIN "Unit" p ON p."unit_code" = c."unit" WHERE c."unit" IS NOT NULL AND c."unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 Inventory.unit
SELECT c.record_uid, c."unit" FROM "Inventory" c LEFT JOIN "Unit" p ON p."unit_code" = c."unit" WHERE c."unit" IS NOT NULL AND c."unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- R07 ProductionPlanLine.unit
SELECT c.record_uid, c."unit" FROM "ProductionPlanLine" c LEFT JOIN "Unit" p ON p."unit_code" = c."unit" WHERE c."unit" IS NOT NULL AND c."unit" <> '' AND (1=1) AND p.record_uid IS NULL;

-- B01 BOMLine.component_product_id
WITH RECURSIVE e AS (SELECT b.product_id AS u, l.component_product_id AS v, l.record_uid AS uid FROM BOMLine l JOIN BOM b ON b.bom_id = l.bom_id WHERE l.component_type = 'PRODUCT' AND l.component_product_id IS NOT NULL), reach(src, dst) AS (SELECT DISTINCT u, v FROM e UNION SELECT r.src, e.v FROM reach r JOIN e ON e.u = r.dst) SELECT DISTINCT e.uid, e.u || '->' || e.v FROM e WHERE e.u = e.v OR EXISTS (SELECT 1 FROM reach r WHERE r.src = e.v AND r.dst = e.u);

-- B02 BOM.*
WITH a AS (SELECT * FROM BOM WHERE status = 'APPROVED' AND is_active = 1 AND (date(valid_from) IS NOT NULL AND date(valid_from) = valid_from) AND (min_qty NOT GLOB '*[^0-9.-]*' AND min_qty GLOB '*[0-9]*' AND min_qty NOT GLOB '?*-*' AND (length(min_qty) - length(replace(min_qty, '.', ''))) <= 1) AND (valid_to IS NULL OR (date(valid_to) IS NOT NULL AND date(valid_to) = valid_to)) AND (max_qty IS NULL OR (max_qty NOT GLOB '*[^0-9.-]*' AND max_qty GLOB '*[0-9]*' AND max_qty NOT GLOB '?*-*' AND (length(max_qty) - length(replace(max_qty, '.', ''))) <= 1))) SELECT x.record_uid, x.bom_id FROM a x JOIN a y ON x.product_id = y.product_id AND x.record_uid <> y.record_uid WHERE x.valid_from <= COALESCE(y.valid_to, '9999-12-31') AND y.valid_from <= COALESCE(x.valid_to, '9999-12-31') AND CAST(x.min_qty AS REAL) < COALESCE(CAST(y.max_qty AS REAL), 1e30) AND CAST(y.min_qty AS REAL) < COALESCE(CAST(x.max_qty AS REAL), 1e30) AND (x.site_id IS NULL OR y.site_id IS NULL OR x.site_id = y.site_id) GROUP BY x.record_uid;

-- B03 BOM.status
SELECT record_uid, status FROM BOM WHERE is_active = 1 AND status IS NOT NULL AND status <> '' AND status <> 'APPROVED';

-- B04 BOM.*
SELECT t.record_uid, t."product_id" || '|' || t."bom_version" FROM "BOM" t JOIN (SELECT "product_id", "bom_version" FROM "BOM" WHERE "product_id" IS NOT NULL AND "product_id" <> '' AND "bom_version" IS NOT NULL AND "bom_version" <> '' GROUP BY "product_id", "bom_version" HAVING COUNT(*) > 1) d USING ("product_id", "bom_version");

-- B05 BOM.valid_to
SELECT record_uid, valid_to FROM BOM WHERE (date(valid_from) IS NOT NULL AND date(valid_from) = valid_from) AND (date(valid_to) IS NOT NULL AND date(valid_to) = valid_to) AND valid_to < valid_from;

-- B05 BOM.max_qty
SELECT record_uid, max_qty FROM BOM WHERE (min_qty NOT GLOB '*[^0-9.-]*' AND min_qty GLOB '*[0-9]*' AND min_qty NOT GLOB '?*-*' AND (length(min_qty) - length(replace(min_qty, '.', ''))) <= 1) AND (max_qty NOT GLOB '*[^0-9.-]*' AND max_qty GLOB '*[0-9]*' AND max_qty NOT GLOB '?*-*' AND (length(max_qty) - length(replace(max_qty, '.', ''))) <= 1) AND CAST(max_qty AS REAL) <= CAST(min_qty AS REAL);

-- B06 ProductionPlanLine.product_id
SELECT l.record_uid, l.product_id FROM ProductionPlanLine l LEFT JOIN BOM b ON b.product_id = l.product_id AND b.status = 'APPROVED' AND b.is_active = 1 AND (date(b.valid_from) IS NOT NULL AND date(b.valid_from) = b.valid_from) AND (b.valid_to IS NULL OR (date(b.valid_to) IS NOT NULL AND date(b.valid_to) = b.valid_to)) AND (b.min_qty NOT GLOB '*[^0-9.-]*' AND b.min_qty GLOB '*[0-9]*' AND b.min_qty NOT GLOB '?*-*' AND (length(b.min_qty) - length(replace(b.min_qty, '.', ''))) <= 1) AND (b.max_qty IS NULL OR (b.max_qty NOT GLOB '*[^0-9.-]*' AND b.max_qty GLOB '*[0-9]*' AND b.max_qty NOT GLOB '?*-*' AND (length(b.max_qty) - length(replace(b.max_qty, '.', ''))) <= 1)) AND b.valid_from <= l.period_start AND l.period_start <= COALESCE(b.valid_to, '9999-12-31') AND CAST(b.min_qty AS REAL) <= CAST(l.planned_qty AS REAL) AND CAST(l.planned_qty AS REAL) < COALESCE(CAST(b.max_qty AS REAL), 1e30) AND b.site_id IS NULL WHERE l.production_mode = 'INHOUSE' AND (date(l.period_start) IS NOT NULL AND date(l.period_start) = l.period_start) AND (l.planned_qty NOT GLOB '*[^0-9.-]*' AND l.planned_qty GLOB '*[0-9]*' AND l.planned_qty NOT GLOB '?*-*' AND (length(l.planned_qty) - length(replace(l.planned_qty, '.', ''))) <= 1) GROUP BY l.record_uid HAVING COUNT(b.record_uid) <> 1;

-- B07 BOMLine.component_type
SELECT record_uid, component_type FROM BOMLine WHERE component_type IN ('MATERIAL', 'PRODUCT') AND ((component_type = 'MATERIAL') <> (component_material_id IS NOT NULL) OR (component_type = 'MATERIAL') = (component_product_id IS NOT NULL));

-- B08 BOMLine.unit
SELECT t.record_uid, t.unit FROM "BOMLine" t JOIN Unit u1 ON u1.unit_code = t.unit JOIN Unit u2 ON u2.unit_code = (CASE WHEN t.component_type = 'MATERIAL' THEN (SELECT base_unit FROM Material WHERE material_id = t.component_material_id) ELSE (SELECT base_unit FROM Product WHERE product_id = t.component_product_id) END) WHERE u1.dimension <> u2.dimension;

-- B08 Order.unit
SELECT t.record_uid, t.unit FROM "Order" t JOIN Unit u1 ON u1.unit_code = t.unit JOIN Unit u2 ON u2.unit_code = (SELECT base_unit FROM Product WHERE product_id = t.product_id) WHERE u1.dimension <> u2.dimension;

-- B08 Inventory.unit
SELECT t.record_uid, t.unit FROM "Inventory" t JOIN Unit u1 ON u1.unit_code = t.unit JOIN Unit u2 ON u2.unit_code = (CASE WHEN t.item_type = 'MATERIAL' THEN (SELECT base_unit FROM Material WHERE material_id = t.item_id) ELSE (SELECT base_unit FROM Product WHERE product_id = t.item_id) END) WHERE u1.dimension <> u2.dimension;

-- B08 ProductionPlanLine.unit
SELECT t.record_uid, t.unit FROM "ProductionPlanLine" t JOIN Unit u1 ON u1.unit_code = t.unit JOIN Unit u2 ON u2.unit_code = (SELECT base_unit FROM Product WHERE product_id = t.product_id) WHERE u1.dimension <> u2.dimension;

-- B09 BOM.*
SELECT record_uid, bom_id FROM BOM b WHERE NOT EXISTS (SELECT 1 FROM BOMLine l WHERE l.bom_id = b.bom_id);

-- B10 BOMLine.*
SELECT l.record_uid, COALESCE(l.component_material_id, l.component_product_id) FROM BOMLine l JOIN (SELECT bom_id, COALESCE(component_material_id, component_product_id) c FROM BOMLine WHERE COALESCE(component_material_id, component_product_id) IS NOT NULL GROUP BY 1, 2 HAVING COUNT(*) > 1) d ON d.bom_id = l.bom_id AND d.c = COALESCE(l.component_material_id, l.component_product_id);

-- B11 SupplierMaterial.is_preferred
SELECT s.record_uid, s.is_preferred FROM SupplierMaterial s JOIN (SELECT material_id FROM SupplierMaterial WHERE material_id IS NOT NULL GROUP BY material_id HAVING SUM(CASE WHEN is_preferred = 1 THEN 1 ELSE 0 END) <> 1) m USING (material_id);

-- B12 SalesHistory.allocation_share
SELECT s.record_uid, s.allocation_share FROM SalesHistory s JOIN (SELECT derived_from_record_uid g FROM SalesHistory WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NOT NULL AND (allocation_share NOT GLOB '*[^0-9.-]*' AND allocation_share GLOB '*[0-9]*' AND allocation_share NOT GLOB '?*-*' AND (length(allocation_share) - length(replace(allocation_share, '.', ''))) <= 1) GROUP BY derived_from_record_uid HAVING ABS(SUM(CAST(allocation_share AS REAL)) - 1) > 0.0005) d ON d.g = s.derived_from_record_uid WHERE s.generation_method = 'ALLOCATED' AND (s.allocation_share NOT GLOB '*[^0-9.-]*' AND s.allocation_share GLOB '*[0-9]*' AND s.allocation_share NOT GLOB '?*-*' AND (length(s.allocation_share) - length(replace(s.allocation_share, '.', ''))) <= 1);

-- B13 SalesHistory.derived_from_record_uid
SELECT record_uid, NULL FROM SalesHistory WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NULL;

-- B13 SalesHistory.allocation_share
SELECT record_uid, NULL FROM SalesHistory WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NOT NULL AND allocation_share IS NULL;

-- B14 Product.outsourcing_unit_cost
SELECT record_uid, outsourcing_unit_cost FROM Product WHERE outsourcing_allowed IN (0, 1) AND (outsourcing_allowed = 1) <> (outsourcing_unit_cost IS NOT NULL);

-- V02 Inventory.allocated_qty
SELECT record_uid, allocated_qty FROM Inventory WHERE (on_hand_qty NOT GLOB '*[^0-9.-]*' AND on_hand_qty GLOB '*[0-9]*' AND on_hand_qty NOT GLOB '?*-*' AND (length(on_hand_qty) - length(replace(on_hand_qty, '.', ''))) <= 1) AND (allocated_qty NOT GLOB '*[^0-9.-]*' AND allocated_qty GLOB '*[0-9]*' AND allocated_qty NOT GLOB '?*-*' AND (length(allocated_qty) - length(replace(allocated_qty, '.', ''))) <= 1) AND CAST(allocated_qty AS REAL) > CAST(on_hand_qty AS REAL);

-- V03 Inventory.on_hand_qty
SELECT record_uid, on_hand_qty FROM Inventory WHERE unit = 'EA' AND (on_hand_qty NOT GLOB '*[^0-9.-]*' AND on_hand_qty GLOB '*[0-9]*' AND on_hand_qty NOT GLOB '?*-*' AND (length(on_hand_qty) - length(replace(on_hand_qty, '.', ''))) <= 1) AND CAST(on_hand_qty AS REAL) <> CAST(CAST(on_hand_qty AS REAL) AS INTEGER);

-- V03 Inventory.allocated_qty
SELECT record_uid, allocated_qty FROM Inventory WHERE unit = 'EA' AND (allocated_qty NOT GLOB '*[^0-9.-]*' AND allocated_qty GLOB '*[0-9]*' AND allocated_qty NOT GLOB '?*-*' AND (length(allocated_qty) - length(replace(allocated_qty, '.', ''))) <= 1) AND CAST(allocated_qty AS REAL) <> CAST(CAST(allocated_qty AS REAL) AS INTEGER);

-- V03 Inventory.on_order_qty
SELECT record_uid, on_order_qty FROM Inventory WHERE unit = 'EA' AND (on_order_qty NOT GLOB '*[^0-9.-]*' AND on_order_qty GLOB '*[0-9]*' AND on_order_qty NOT GLOB '?*-*' AND (length(on_order_qty) - length(replace(on_order_qty, '.', ''))) <= 1) AND CAST(on_order_qty AS REAL) <> CAST(CAST(on_order_qty AS REAL) AS INTEGER);

-- V04 Inventory.*
SELECT t.record_uid, t."item_type" || '|' || t."item_id" || '|' || t."as_of_date" FROM "Inventory" t JOIN (SELECT "item_type", "item_id", "as_of_date" FROM "Inventory" WHERE "item_type" IS NOT NULL AND "item_type" <> '' AND "item_id" IS NOT NULL AND "item_id" <> '' AND "as_of_date" IS NOT NULL AND "as_of_date" <> '' GROUP BY "item_type", "item_id", "as_of_date" HAVING COUNT(*) > 1) d USING ("item_type", "item_id", "as_of_date");

-- V05 Inventory.expected_receipt_date
SELECT record_uid, NULL FROM Inventory WHERE (on_order_qty NOT GLOB '*[^0-9.-]*' AND on_order_qty GLOB '*[0-9]*' AND on_order_qty NOT GLOB '?*-*' AND (length(on_order_qty) - length(replace(on_order_qty, '.', ''))) <= 1) AND CAST(on_order_qty AS REAL) > 0 AND expected_receipt_date IS NULL;

-- V06 Inventory.as_of_date
SELECT record_uid, as_of_date FROM Inventory WHERE (date(as_of_date) IS NOT NULL AND date(as_of_date) = as_of_date) AND as_of_date > '2026-11-15';

-- V07 Order.due_date
SELECT record_uid, due_date FROM "Order" WHERE (date(order_date) IS NOT NULL AND date(order_date) = order_date) AND (date(due_date) IS NOT NULL AND date(due_date) = due_date) AND due_date < order_date;

-- V08 Order.product_id
SELECT record_uid, product_id FROM "Order" o WHERE status = 'OPEN' AND product_id IS NOT NULL AND product_id <> '' AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = o.product_id);

-- V08 ProductionPlanLine.product_id
SELECT record_uid, product_id FROM ProductionPlanLine l WHERE production_mode = 'INHOUSE' AND product_id IS NOT NULL AND product_id <> '' AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id);

-- V09 ProductionPlanLine.resource_id
SELECT record_uid, resource_id FROM ProductionPlanLine l WHERE production_mode = 'INHOUSE' AND resource_id IS NOT NULL AND EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id) AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id AND p.resource_id = l.resource_id);

-- V10 ProductionPlanLine.resource_id
SELECT record_uid, resource_id FROM ProductionPlanLine WHERE production_mode IN ('INHOUSE', 'OUTSOURCE') AND (production_mode = 'OUTSOURCE') <> (resource_id IS NULL);

-- V11 ProductionPlanLine.production_mode
SELECT l.record_uid, l.production_mode FROM ProductionPlanLine l JOIN Product p ON p.product_id = l.product_id WHERE l.production_mode = 'OUTSOURCE' AND p.outsourcing_allowed = 0;

-- V12 ProductionPlanLine.period_start
SELECT l.record_uid, l.period_start FROM ProductionPlanLine l JOIN ProductionPlan p ON p.plan_id = l.plan_id WHERE (date(l.period_start) IS NOT NULL AND date(l.period_start) = l.period_start) AND (date(p.horizon_start) IS NOT NULL AND date(p.horizon_start) = p.horizon_start) AND (date(p.horizon_end) IS NOT NULL AND date(p.horizon_end) = p.horizon_end) AND (l.period_start < p.horizon_start OR l.period_start > p.horizon_end);

-- V13 생산능력 (자원·주별 필요시간)
SELECT l.plan_id, o.resource_id, l.period_start, SUM(CAST(l.planned_qty AS REAL) * CAST(o.run_time_per_unit_h AS REAL) + COALESCE(CAST(o.setup_time_h AS REAL), 0)) req, CAST(r.regular_hours_per_day AS REAL) * 5 + CASE WHEN p.overtime_allowed = 1 THEN CAST(r.overtime_hours_per_day_max AS REAL) * 5 ELSE 0 END cap FROM ProductionPlanLine l JOIN ProductionPlan p ON p.plan_id = l.plan_id JOIN Operation o ON o.product_id = l.product_id JOIN Resource r ON r.resource_id = o.resource_id WHERE l.production_mode = 'INHOUSE' AND (l.planned_qty NOT GLOB '*[^0-9.-]*' AND l.planned_qty GLOB '*[0-9]*' AND l.planned_qty NOT GLOB '?*-*' AND (length(l.planned_qty) - length(replace(l.planned_qty, '.', ''))) <= 1) AND (o.run_time_per_unit_h NOT GLOB '*[^0-9.-]*' AND o.run_time_per_unit_h GLOB '*[0-9]*' AND o.run_time_per_unit_h NOT GLOB '?*-*' AND (length(o.run_time_per_unit_h) - length(replace(o.run_time_per_unit_h, '.', ''))) <= 1) GROUP BY l.plan_id, o.resource_id, l.period_start ORDER BY 1, 2, 3;

-- constraints 모드 DDL
CREATE TABLE "Unit" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "unit_code" TEXT CONSTRAINT S01__unit_code__0 NOT NULL, "dimension" TEXT CONSTRAINT S01__dimension__0 NOT NULL CONSTRAINT S04__dimension__0 CHECK ("dimension" IS NULL OR "dimension" IN ('MASS', 'COUNT', 'TIME')), "base_unit_code" TEXT CONSTRAINT S01__base_unit_code__0 NOT NULL, "to_base_factor" REAL CONSTRAINT S01__to_base_factor__0 NOT NULL CONSTRAINT S06__to_base_factor__gt CHECK ("to_base_factor" IS NULL OR "to_base_factor" > 0), CONSTRAINT PK_Unit PRIMARY KEY (unit_code)) STRICT;
CREATE TABLE "Product" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "product_name" TEXT CONSTRAINT S01__product_name__0 NOT NULL, "product_type" TEXT CONSTRAINT S01__product_type__0 NOT NULL CONSTRAINT S04__product_type__0 CHECK ("product_type" IS NULL OR "product_type" IN ('FINISHED', 'SEMI_FINISHED')), "base_unit" TEXT CONSTRAINT S01__base_unit__0 NOT NULL, "safety_stock_qty" REAL CONSTRAINT S01__safety_stock_qty__0 NOT NULL CONSTRAINT S06__safety_stock_qty__ge CHECK ("safety_stock_qty" IS NULL OR "safety_stock_qty" >= 0), "manuf_lead_time_days" INTEGER CONSTRAINT S01__manuf_lead_time_days__0 NOT NULL CONSTRAINT S06__manuf_lead_time_days__ge CHECK ("manuf_lead_time_days" IS NULL OR "manuf_lead_time_days" >= 0), "outsourcing_allowed" INTEGER CONSTRAINT S01__outsourcing_allowed__0 NOT NULL CONSTRAINT S02__outsourcing_allowed__0 CHECK ("outsourcing_allowed" IS NULL OR "outsourcing_allowed" IN (0, 1)), "outsourcing_unit_cost" REAL CONSTRAINT S06__outsourcing_unit_cost__ge CHECK ("outsourcing_unit_cost" IS NULL OR "outsourcing_unit_cost" >= 0), CONSTRAINT PK_Product PRIMARY KEY (product_id), CONSTRAINT B14__outsourcing_unit_cost__c0 CHECK ((outsourcing_allowed = 1) = (outsourcing_unit_cost IS NOT NULL)), FOREIGN KEY ("base_unit") REFERENCES "Unit"("unit_code")) STRICT;
CREATE TABLE "Material" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "material_id" TEXT CONSTRAINT S01__material_id__0 NOT NULL, "material_name" TEXT CONSTRAINT S01__material_name__0 NOT NULL, "base_unit" TEXT CONSTRAINT S01__base_unit__0 NOT NULL, "unit_cost" REAL CONSTRAINT S01__unit_cost__0 NOT NULL CONSTRAINT S06__unit_cost__ge CHECK ("unit_cost" IS NULL OR "unit_cost" >= 0), "safety_stock_qty" REAL CONSTRAINT S01__safety_stock_qty__0 NOT NULL CONSTRAINT S06__safety_stock_qty__ge CHECK ("safety_stock_qty" IS NULL OR "safety_stock_qty" >= 0), CONSTRAINT PK_Material PRIMARY KEY (material_id), FOREIGN KEY ("base_unit") REFERENCES "Unit"("unit_code")) STRICT;
CREATE TABLE "Supplier" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "supplier_id" TEXT CONSTRAINT S01__supplier_id__0 NOT NULL, "supplier_name" TEXT CONSTRAINT S01__supplier_name__0 NOT NULL, CONSTRAINT PK_Supplier PRIMARY KEY (supplier_id)) STRICT;
CREATE TABLE "Resource" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "resource_id" TEXT CONSTRAINT S01__resource_id__0 NOT NULL, "resource_name" TEXT CONSTRAINT S01__resource_name__0 NOT NULL, "resource_type" TEXT CONSTRAINT S01__resource_type__0 NOT NULL CONSTRAINT S04__resource_type__0 CHECK ("resource_type" IS NULL OR "resource_type" IN ('MACHINE', 'LINE', 'WORKCENTER')), "regular_hours_per_day" REAL CONSTRAINT S01__regular_hours_per_day__0 NOT NULL CONSTRAINT S06__regular_hours_per_day__gt CHECK ("regular_hours_per_day" IS NULL OR "regular_hours_per_day" > 0), "overtime_hours_per_day_max" REAL CONSTRAINT S01__overtime_hours_per_day_max__0 NOT NULL CONSTRAINT S06__overtime_hours_per_day_max__ge CHECK ("overtime_hours_per_day_max" IS NULL OR "overtime_hours_per_day_max" >= 0), "cost_per_hour" REAL CONSTRAINT S01__cost_per_hour__0 NOT NULL CONSTRAINT S06__cost_per_hour__ge CHECK ("cost_per_hour" IS NULL OR "cost_per_hour" >= 0), "overtime_cost_per_hour" REAL CONSTRAINT S01__overtime_cost_per_hour__0 NOT NULL CONSTRAINT S06__overtime_cost_per_hour__ge CHECK ("overtime_cost_per_hour" IS NULL OR "overtime_cost_per_hour" >= 0), CONSTRAINT PK_Resource PRIMARY KEY (resource_id)) STRICT;
CREATE TABLE "SupplierMaterial" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "supplier_id" TEXT CONSTRAINT S01__supplier_id__0 NOT NULL, "material_id" TEXT CONSTRAINT S01__material_id__0 NOT NULL, "lead_time_days" INTEGER CONSTRAINT S01__lead_time_days__0 NOT NULL CONSTRAINT S06__lead_time_days__ge CHECK ("lead_time_days" IS NULL OR "lead_time_days" >= 0), "min_order_qty" REAL CONSTRAINT S06__min_order_qty__ge CHECK ("min_order_qty" IS NULL OR "min_order_qty" >= 0), "is_preferred" INTEGER CONSTRAINT S01__is_preferred__0 NOT NULL CONSTRAINT S02__is_preferred__0 CHECK ("is_preferred" IS NULL OR "is_preferred" IN (0, 1)), CONSTRAINT PK_SupplierMaterial PRIMARY KEY (supplier_id, material_id), FOREIGN KEY ("supplier_id") REFERENCES "Supplier"("supplier_id"), FOREIGN KEY ("material_id") REFERENCES "Material"("material_id")) STRICT;
CREATE TABLE "BOM" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "bom_id" TEXT CONSTRAINT S01__bom_id__0 NOT NULL, "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "bom_version" TEXT CONSTRAINT S01__bom_version__0 NOT NULL, "status" TEXT CONSTRAINT S01__status__0 NOT NULL CONSTRAINT S04__status__0 CHECK ("status" IS NULL OR "status" IN ('DRAFT', 'APPROVED')), "is_active" INTEGER CONSTRAINT S01__is_active__0 NOT NULL CONSTRAINT S02__is_active__0 CHECK ("is_active" IS NULL OR "is_active" IN (0, 1)), "valid_from" TEXT CONSTRAINT S01__valid_from__0 NOT NULL CONSTRAINT S03__valid_from__0 CHECK ("valid_from" IS NULL OR (date("valid_from") IS NOT NULL AND date("valid_from") = "valid_from")), "valid_to" TEXT CONSTRAINT S03__valid_to__0 CHECK ("valid_to" IS NULL OR (date("valid_to") IS NOT NULL AND date("valid_to") = "valid_to")), "min_qty" REAL CONSTRAINT S01__min_qty__0 NOT NULL CONSTRAINT S06__min_qty__ge CHECK ("min_qty" IS NULL OR "min_qty" >= 0), "max_qty" REAL, "site_id" TEXT, "base_qty" REAL CONSTRAINT S01__base_qty__0 NOT NULL CONSTRAINT S06__base_qty__gt CHECK ("base_qty" IS NULL OR "base_qty" > 0), CONSTRAINT PK_BOM PRIMARY KEY (bom_id), CONSTRAINT B03__status__c0 CHECK (NOT (is_active = 1 AND status <> 'APPROVED')), CONSTRAINT B05__valid_to__c1 CHECK (valid_to IS NULL OR valid_to >= valid_from), CONSTRAINT B05__max_qty__c2 CHECK (max_qty IS NULL OR max_qty > min_qty), FOREIGN KEY ("product_id") REFERENCES "Product"("product_id")) STRICT;
CREATE TABLE "BOMLine" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "bom_id" TEXT CONSTRAINT S01__bom_id__0 NOT NULL, "line_no" INTEGER CONSTRAINT S01__line_no__0 NOT NULL CONSTRAINT S06__line_no__ge CHECK ("line_no" IS NULL OR "line_no" >= 1), "component_type" TEXT CONSTRAINT S01__component_type__0 NOT NULL CONSTRAINT S04__component_type__0 CHECK ("component_type" IS NULL OR "component_type" IN ('MATERIAL', 'PRODUCT')), "component_material_id" TEXT, "component_product_id" TEXT, "qty_per" REAL CONSTRAINT S01__qty_per__0 NOT NULL CONSTRAINT S06__qty_per__gt CHECK ("qty_per" IS NULL OR "qty_per" > 0), "unit" TEXT CONSTRAINT S01__unit__0 NOT NULL, "scrap_rate" REAL CONSTRAINT S06__scrap_rate__ge CHECK ("scrap_rate" IS NULL OR "scrap_rate" >= 0) CONSTRAINT S06__scrap_rate__lt CHECK ("scrap_rate" IS NULL OR "scrap_rate" < 1), "line_type" TEXT CONSTRAINT S04__line_type__0 CHECK ("line_type" IS NULL OR "line_type" IN ('ITEM')), CONSTRAINT PK_BOMLine PRIMARY KEY (bom_id, line_no), CONSTRAINT B07__component_type__c0 CHECK ((component_type = 'MATERIAL') = (component_material_id IS NOT NULL) AND (component_type = 'PRODUCT') = (component_product_id IS NOT NULL)), FOREIGN KEY ("bom_id") REFERENCES "BOM"("bom_id"), FOREIGN KEY ("component_material_id") REFERENCES "Material"("material_id"), FOREIGN KEY ("component_product_id") REFERENCES "Product"("product_id"), FOREIGN KEY ("unit") REFERENCES "Unit"("unit_code")) STRICT;
CREATE TABLE "Order" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "order_id" TEXT CONSTRAINT S01__order_id__0 NOT NULL, "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "order_qty" REAL CONSTRAINT S01__order_qty__0 NOT NULL CONSTRAINT S06__order_qty__gt CHECK ("order_qty" IS NULL OR "order_qty" > 0), "unit" TEXT CONSTRAINT S01__unit__0 NOT NULL, "order_date" TEXT CONSTRAINT S01__order_date__0 NOT NULL CONSTRAINT S03__order_date__0 CHECK ("order_date" IS NULL OR (date("order_date") IS NOT NULL AND date("order_date") = "order_date")), "due_date" TEXT CONSTRAINT S01__due_date__0 NOT NULL CONSTRAINT S03__due_date__0 CHECK ("due_date" IS NULL OR (date("due_date") IS NOT NULL AND date("due_date") = "due_date")), "priority" TEXT CONSTRAINT S01__priority__0 NOT NULL CONSTRAINT S04__priority__0 CHECK ("priority" IS NULL OR "priority" IN ('NORMAL', 'URGENT')), "status" TEXT CONSTRAINT S01__status__0 NOT NULL CONSTRAINT S04__status__0 CHECK ("status" IS NULL OR "status" IN ('OPEN', 'CLOSED', 'CANCELLED')), CONSTRAINT PK_Order PRIMARY KEY (order_id), CONSTRAINT V07__due_date__c0 CHECK (due_date >= order_date), FOREIGN KEY ("product_id") REFERENCES "Product"("product_id"), FOREIGN KEY ("unit") REFERENCES "Unit"("unit_code")) STRICT;
CREATE TABLE "SalesHistory" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "period_start" TEXT CONSTRAINT S01__period_start__0 NOT NULL CONSTRAINT S03__period_start__0 CHECK ("period_start" IS NULL OR (date("period_start") IS NOT NULL AND date("period_start") = "period_start")), "period_grain" TEXT CONSTRAINT S01__period_grain__0 NOT NULL CONSTRAINT S04__period_grain__0 CHECK ("period_grain" IS NULL OR "period_grain" IN ('DAY', 'WEEK')), "sales_qty" REAL CONSTRAINT S01__sales_qty__0 NOT NULL CONSTRAINT S06__sales_qty__ge CHECK ("sales_qty" IS NULL OR "sales_qty" >= 0), "source_series_id" TEXT, "generation_method" TEXT CONSTRAINT S01__generation_method__0 NOT NULL CONSTRAINT S04__generation_method__0 CHECK ("generation_method" IS NULL OR "generation_method" IN ('GENERATED', 'ALLOCATED', 'MAPPED', 'TRANSFORMED')), "derived_from_record_uid" TEXT, "allocation_share" REAL CONSTRAINT S06__allocation_share__gt CHECK ("allocation_share" IS NULL OR "allocation_share" > 0) CONSTRAINT S06__allocation_share__le CHECK ("allocation_share" IS NULL OR "allocation_share" <= 1), "date_is_synthetic" INTEGER CONSTRAINT S02__date_is_synthetic__0 CHECK ("date_is_synthetic" IS NULL OR "date_is_synthetic" IN (0, 1)), "source_day_of_week_code" INTEGER, CONSTRAINT PK_SalesHistory PRIMARY KEY (product_id, period_start, period_grain), CONSTRAINT B13__derived_from_record_uid__c0 CHECK (generation_method <> 'ALLOCATED' OR (derived_from_record_uid IS NOT NULL AND allocation_share IS NOT NULL)), FOREIGN KEY ("product_id") REFERENCES "Product"("product_id")) STRICT;
CREATE TABLE "Inventory" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "item_type" TEXT CONSTRAINT S01__item_type__0 NOT NULL CONSTRAINT S04__item_type__0 CHECK ("item_type" IS NULL OR "item_type" IN ('PRODUCT', 'MATERIAL')), "item_id" TEXT CONSTRAINT S01__item_id__0 NOT NULL, "as_of_date" TEXT CONSTRAINT S01__as_of_date__0 NOT NULL CONSTRAINT S03__as_of_date__0 CHECK ("as_of_date" IS NULL OR (date("as_of_date") IS NOT NULL AND date("as_of_date") = "as_of_date")), "on_hand_qty" REAL CONSTRAINT S01__on_hand_qty__0 NOT NULL CONSTRAINT V01__on_hand_qty__ge CHECK ("on_hand_qty" IS NULL OR "on_hand_qty" >= 0), "allocated_qty" REAL CONSTRAINT S06__allocated_qty__ge CHECK ("allocated_qty" IS NULL OR "allocated_qty" >= 0), "on_order_qty" REAL CONSTRAINT S06__on_order_qty__ge CHECK ("on_order_qty" IS NULL OR "on_order_qty" >= 0), "expected_receipt_date" TEXT CONSTRAINT S03__expected_receipt_date__0 CHECK ("expected_receipt_date" IS NULL OR (date("expected_receipt_date") IS NOT NULL AND date("expected_receipt_date") = "expected_receipt_date")), "unit" TEXT CONSTRAINT S01__unit__0 NOT NULL, CONSTRAINT PK_Inventory PRIMARY KEY (item_type, item_id, as_of_date), CONSTRAINT V02__allocated_qty__c0 CHECK (allocated_qty IS NULL OR allocated_qty <= on_hand_qty), CONSTRAINT V05__expected_receipt_date__c1 CHECK (NOT (on_order_qty > 0 AND expected_receipt_date IS NULL)), CONSTRAINT V06__as_of_date__c2 CHECK (as_of_date <= '2026-11-15'), CONSTRAINT V03__on_hand_qty__c3 CHECK (unit <> 'EA' OR (on_hand_qty = CAST(on_hand_qty AS INTEGER))), FOREIGN KEY ("unit") REFERENCES "Unit"("unit_code")) STRICT;
CREATE TABLE "Operation" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "operation_id" TEXT CONSTRAINT S01__operation_id__0 NOT NULL, "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "sequence_no" INTEGER CONSTRAINT S01__sequence_no__0 NOT NULL CONSTRAINT S06__sequence_no__ge CHECK ("sequence_no" IS NULL OR "sequence_no" >= 1), "resource_id" TEXT CONSTRAINT S01__resource_id__0 NOT NULL, "run_time_per_unit_h" REAL CONSTRAINT S01__run_time_per_unit_h__0 NOT NULL CONSTRAINT S06__run_time_per_unit_h__gt CHECK ("run_time_per_unit_h" IS NULL OR "run_time_per_unit_h" > 0), "setup_time_h" REAL CONSTRAINT S01__setup_time_h__0 NOT NULL CONSTRAINT S06__setup_time_h__ge CHECK ("setup_time_h" IS NULL OR "setup_time_h" >= 0), CONSTRAINT PK_Operation PRIMARY KEY (operation_id), FOREIGN KEY ("product_id") REFERENCES "Product"("product_id"), FOREIGN KEY ("resource_id") REFERENCES "Resource"("resource_id")) STRICT;
CREATE TABLE "ProductionPlan" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "plan_id" TEXT CONSTRAINT S01__plan_id__0 NOT NULL, "plan_name" TEXT CONSTRAINT S01__plan_name__0 NOT NULL, "horizon_start" TEXT CONSTRAINT S01__horizon_start__0 NOT NULL CONSTRAINT S03__horizon_start__0 CHECK ("horizon_start" IS NULL OR (date("horizon_start") IS NOT NULL AND date("horizon_start") = "horizon_start")), "horizon_end" TEXT CONSTRAINT S01__horizon_end__0 NOT NULL CONSTRAINT S03__horizon_end__0 CHECK ("horizon_end" IS NULL OR (date("horizon_end") IS NOT NULL AND date("horizon_end") = "horizon_end")), "generated_by" TEXT CONSTRAINT S01__generated_by__0 NOT NULL CONSTRAINT S04__generated_by__0 CHECK ("generated_by" IS NULL OR "generated_by" IN ('RULE', 'OPTIMIZER', 'MANUAL')), "overtime_allowed" INTEGER CONSTRAINT S01__overtime_allowed__0 NOT NULL CONSTRAINT S02__overtime_allowed__0 CHECK ("overtime_allowed" IS NULL OR "overtime_allowed" IN (0, 1)), CONSTRAINT PK_ProductionPlan PRIMARY KEY (plan_id)) STRICT;
CREATE TABLE "ProductionPlanLine" (record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB 'rec_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'), origin_class TEXT NOT NULL, "plan_id" TEXT CONSTRAINT S01__plan_id__0 NOT NULL, "line_no" INTEGER CONSTRAINT S01__line_no__0 NOT NULL CONSTRAINT S06__line_no__ge CHECK ("line_no" IS NULL OR "line_no" >= 1), "product_id" TEXT CONSTRAINT S01__product_id__0 NOT NULL, "period_start" TEXT CONSTRAINT S01__period_start__0 NOT NULL CONSTRAINT S03__period_start__0 CHECK ("period_start" IS NULL OR (date("period_start") IS NOT NULL AND date("period_start") = "period_start")), "planned_qty" REAL CONSTRAINT S01__planned_qty__0 NOT NULL CONSTRAINT S06__planned_qty__ge CHECK ("planned_qty" IS NULL OR "planned_qty" >= 0), "unit" TEXT CONSTRAINT S01__unit__0 NOT NULL, "production_mode" TEXT CONSTRAINT S01__production_mode__0 NOT NULL CONSTRAINT S04__production_mode__0 CHECK ("production_mode" IS NULL OR "production_mode" IN ('INHOUSE', 'OUTSOURCE')), "resource_id" TEXT, CONSTRAINT PK_ProductionPlanLine PRIMARY KEY (plan_id, line_no), CONSTRAINT V10__resource_id__c0 CHECK ((production_mode = 'OUTSOURCE') = (resource_id IS NULL)), FOREIGN KEY ("plan_id") REFERENCES "ProductionPlan"("plan_id"), FOREIGN KEY ("product_id") REFERENCES "Product"("product_id"), FOREIGN KEY ("resource_id") REFERENCES "Resource"("resource_id"), FOREIGN KEY ("unit") REFERENCES "Unit"("unit_code")) STRICT;
