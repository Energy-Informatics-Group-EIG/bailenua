<?php
/*
 * Baile Nua viewer configuration.
 *
 * Copy to config.php and place it OUTSIDE the public web root, e.g.
 *   /home/<account>/baile_private/config.php
 * then set BAILE_CONFIG in api.php / index.php if the path differs.
 *
 * Use a B2 application key that is READ-ONLY, limited to bucket hrsd-occupants,
 * prefix v1/, with "Allow List All Bucket Names" unticked.
 */
return array(
    'endpoint'      => 's3.eu-central-003.backblazeb2.com',
    'region'        => 'eu-central-003',
    'bucket'        => 'hrsd-occupants',
    'key_id'        => 'PUT_KEY_ID_HERE',
    'app_key'       => 'PUT_APPLICATION_KEY_HERE',

    // Only keys under these prefixes can be listed, read or presigned.
    'allowed_prefixes' => array('v1/'),
    'figures_prefix'   => 'v1/figures/',

    // Optional: read figure JSON from a local folder (e.g. copied from ~/hrsd_occupants/figures)
    // instead of B2. Leave '' to read from v1/figures/ on B2.
    'local_figures_dir' => '',

    // Cache for figure JSON (outside web root, writable by PHP).
    'cache_dir'     => __DIR__ . '/cache',
    'cache_ttl_s'   => 86400,

    // Viewer password. Generate with:  php -r "echo password_hash('your-password', PASSWORD_DEFAULT);"
    // Leave empty ('') to disable the login (not recommended on a public site).
    'password_hash' => '',
);
