fn main() {
    let proto = "../../../../proto/scoring.proto";
    println!("cargo:rerun-if-changed={}", proto);
    prost_build::compile_protos(&[proto], &["../../../../proto"]).expect("compile protos");
}
